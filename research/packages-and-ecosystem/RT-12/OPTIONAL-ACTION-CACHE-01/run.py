"""Check optional cache transport without extending the inner package verifier."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import platform
import runpy
import subprocess
from tempfile import TemporaryDirectory
from zipfile import ZIP_STORED, ZipFile, ZipInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BASELINE = "5ab667bbbe59cde3c9c2777b0155aeadaf0df7b7"
STATIC_PATH = HERE.parent / "STATIC-INDEX-01/run.py"
STATIC = runpy.run_path(str(STATIC_PATH))
from cache_index import CACHE_SCHEMA, expected_action_key, validate_cache_index
from package_identity import PackageFormatError, parse_hash
from test_language_version_cache_index import COMPONENTS, sample_record

CORE = "package.llpkg"
INDEX = "cache/index.json"


def json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def sha(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def encode_index(*records):
    return json_bytes({"schema": CACHE_SCHEMA, "schema_version": 1,
                       "records": sorted(records, key=lambda row: row["action_key"])})


def artifact_path(digest):
    parse_hash(digest)
    return "cache/artifacts/" + digest.split(":", 1)[1]


def carrier(path, members):
    with ZipFile(path, "w", compression=ZIP_STORED) as archive:
        for name, data in sorted(members.items()):
            archive.writestr(ZipInfo(name), data)


def checked_core(payload, directory):
    core = directory / "core-check.llpkg"
    core.write_bytes(payload)
    try:
        assert STATIC["verify_archive"](core, max_records_in_memory=2)
    except STATIC["ArchiveError"]:
        return None
    with ZipFile(core) as package:
        manifest = STATIC["parse_manifest"](package.read("manifest.toml"))
    return {"package_root": manifest["content"]["content_root"],
            "logical_index": manifest["index"]["logical_hash"], "core_archive": sha(payload)}


def cache_lookup(outer, hint, wanted_key, trusted, external):
    if hint is None:
        return "absent"
    try:
        index = validate_cache_index(json.loads(hint), COMPONENTS)
    except (json.JSONDecodeError, PackageFormatError):
        return "invalid-index"
    exact = [row for row in index["records"] if row["action_key"] == wanted_key]
    if not exact:
        return "action-miss"
    row, = exact
    artifacts = row["output_artifacts"]
    if row["status"] != "success" or trusted.get(wanted_key) != artifacts:
        return "untrusted-result"
    artifact, = artifacts
    name = artifact_path(artifact)
    if name in outer.namelist():
        payload, delivery = outer.read(name), "embedded"
    elif artifact in external:
        payload, delivery = external[artifact], "external"
    else:
        return "missing-artifact"
    if sha(payload) != artifact:
        return "artifact-digest-mismatch"
    return "hit-" + delivery


def evaluate(path, directory, detached, wanted, trusted, external):
    with ZipFile(path) as outer:
        names = outer.namelist()
        assert len(names) == len(set(names)) and CORE in names
        identity = checked_core(outer.read(CORE), directory)
        if identity is None:
            return {"package": "refused", "cache": "not-read", "fallback": False}
        assert detached is None or INDEX not in names
        hint = outer.read(INDEX) if INDEX in names else detached
        cache = cache_lookup(outer, hint, wanted, trusted, external)
        return {"package": "admitted", "identity": identity, "cache": cache,
                "fallback": not cache.startswith("hit-")}


def experiment(directory):
    archive = directory / "base.llpkg"
    STATIC["static_archive"](archive, STATIC["sample_index"]())
    good_core = archive.read_bytes()
    root = checked_core(good_core, directory)["package_root"]
    correct_result = b"type-check fixture completed\n"
    wrong_result = b"a different synthetic output\n"
    current = sample_record(input_hashes=[root, STATIC["H1"], STATIC["H2"]],
                            output_artifacts=[sha(correct_result)])
    action = current["action_key"]
    trusted = {action: current["output_artifacts"]}
    old = deepcopy(current)
    old["toolchain_identity"] = sha(b"previous toolchain")
    old["action_key"] = expected_action_key(old, COMPONENTS)
    wrong = current | {"output_artifacts": [sha(wrong_result)]}
    assert expected_action_key(wrong, COMPONENTS) == action
    invalid = current | {"dependency_complete": False}
    payload = {artifact_path(sha(correct_result)): correct_result}
    index = encode_index(current)
    core = {CORE: good_core}
    corrupt = directory / "corrupt.llpkg"
    STATIC["corrupt_payload"](archive, corrupt)

    configurations = {
        "core-only": (core, None, trusted, {}, "absent"),
        "embedded-both": (core | {INDEX: index} | payload, None, trusted, {}, "hit-embedded"),
        "detached-index": (core | payload, index, trusted, {}, "hit-embedded"),
        "embedded-index-external-artifact": (
            core | {INDEX: index}, None, trusted, {sha(correct_result): correct_result}, "hit-external",
        ),
        "no-artifact": (core | {INDEX: index}, None, trusted, {}, "missing-artifact"),
        "payload-without-index": (core | payload, None, trusted, {}, "absent"),
        "stale-toolchain-key": (core | {INDEX: encode_index(old)} | payload, None, trusted, {}, "action-miss"),
        "incomplete-action": (core | {INDEX: encode_index(invalid)} | payload, None, trusted, {}, "invalid-index"),
        "unreadable-index": (core | {INDEX: b"{"}, None, trusted, {}, "invalid-index"),
        "corrupt-artifact": (
            core | {INDEX: index, artifact_path(sha(correct_result)): wrong_result},
            None, trusted, {}, "artifact-digest-mismatch",
        ),
        "untrusted-authority": (core | {INDEX: index} | payload, None, {}, {}, "untrusted-result"),
        "same-key-different-result": (
            core | {INDEX: encode_index(wrong), artifact_path(sha(wrong_result)): wrong_result},
            None, trusted, {}, "untrusted-result",
        ),
        "broken-package-with-valid-cache": (
            {CORE: corrupt.read_bytes(), INDEX: index} | payload, None, trusted, {}, "not-read",
        ),
    }
    rows = {}
    for name, (members, detached, authority, external, expected) in configurations.items():
        path = directory / (name + ".zip")
        carrier(path, members)
        result = evaluate(path, directory, detached, action, authority, external)
        assert result["cache"] == expected
        if name == "broken-package-with-valid-cache":
            assert result["package"] == "refused" and not result["fallback"]
        else:
            assert result["identity"] == checked_core(good_core, directory)
            assert result["fallback"] == (not expected.startswith("hit-"))
        rows[name] = {"archive": sha(path.read_bytes()), "entries": sorted(members),
                      "detached_index": sha(detached) if detached is not None else None, **result}
    for left, right in (
        ("detached-index", "payload-without-index"),
        ("embedded-index-external-artifact", "no-artifact"),
        ("embedded-both", "untrusted-authority"),
    ):
        assert rows[left]["archive"] == rows[right]["archive"]
        assert rows[left]["cache"] != rows[right]["cache"]
    assert len({row["archive"] for row in rows.values()}) == 10
    return {"package_members": sorted(core), "action_request": current, "prior_request": old,
            "rows": rows}


def main():
    sources = [
        STATIC_PATH,
        *(STATIC["PACKAGE_INDEX"] / name for name in (
            "package_archive.py", "package_index.py", "test_package_archive.py")),
        *(STATIC["PACKAGE_IDENTITY"] / name for name in (
            "cache_index.py", "language_version.py", "package_identity.py",
            "test_language_version_cache_index.py")),
    ]
    pins = {}
    for source in sources:
        relative = str(source.relative_to(ROOT))
        archived = subprocess.check_output(["git", "show", f"{BASELINE}:{relative}"], cwd=ROOT)
        assert archived == source.read_bytes(), relative
        pins[relative] = sha(archived)
    with TemporaryDirectory(prefix="llmlang-optional-cache-") as path:
        result = experiment(Path(path))
    print(json.dumps({
        "baseline": BASELINE, "python": platform.python_version(),
        "runner_sha256": sha(Path(__file__).read_bytes()), "source_sha256": pins, **result,
    }, indent=2))


if __name__ == "__main__":
    main()
