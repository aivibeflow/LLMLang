"""Verify static packages and a detached human index derived from exact machine tables."""

import argparse
from copy import deepcopy
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile


HERE = Path(__file__).resolve().parent
PACKAGE_INDEX = HERE.parents[1] / "PROTOTYPES" / "PACKAGE-INDEX-01"
PACKAGE_IDENTITY = PACKAGE_INDEX.with_name("PACKAGE-IDENTITY-01")
sys.path[:0] = [str(PACKAGE_INDEX), str(PACKAGE_IDENTITY)]
from package_archive import ArchiveError, build_archive, verify_archive
from package_identity import logical_index_hash, package_content_root, parse_manifest
from package_index import TABLES, normalize
from test_package_archive import H1, H2, payloads, sample_index, streams


MARKDOWN_SYNTAX = frozenset("|\r\n`[]()!#*_~\\")


def plain_cell(text):
    return "".join(f"&#{ord(char)};" if char in MARKDOWN_SYNTAX else escape(char)
                   for char in text)


def finish_manifest(index, name, table_path):
    placeholder = "sha256:" + "0" * 64
    raw = f'''format = "llmlang.package"
schema_version = 1

[package]
name = "{name}"
version = "0.1.0"

[content]
roots = ["{H1}"]
dependency_policy = "closure"
content_root = "{placeholder}"

[index]
path = "{table_path}"
format_version = 1
logical_hash = "{logical_index_hash(index)}"
'''.encode()
    digest = package_content_root(parse_manifest(raw), index)
    return raw.replace(placeholder.encode(), digest.encode())


def static_archive(path, index, name="fixture-package", table_path="index"):
    build_archive(finish_manifest(index, name, table_path), streams(index), payloads(), path,
                  max_records_in_memory=2)


def render(path):
    # Reuse one private byte image for verification and subsequent projection.
    with TemporaryDirectory(prefix="llmlang-static-index-view-") as scratch:
        pinned = Path(scratch) / "pinned.llpkg"
        shutil.copyfile(path, pinned)
        if not verify_archive(pinned, max_records_in_memory=2):
            raise ArchiveError("archive verification failed")
        with ZipFile(pinned) as archive:
            manifest = parse_manifest(archive.read("manifest.toml"))
            directory = manifest["index"]["path"]
            tables = {name: [json.loads(line) for line in archive.read(
                f"{directory}/{name}.jsonl").splitlines()] for name in TABLES}

    root = manifest["content"]["content_root"]
    index_hash = manifest["index"]["logical_hash"]
    lines = [
        "# Package index",
        "",
        f"Package root: `{root}`",
        "",
        f"Logical index: `{index_hash}`",
        "",
        "## Contents",
        "",
        "| Table | Records |",
        "|---|---:|",
        *(f"| {name.capitalize()} | {len(tables[name])} |" for name in TABLES),
        "",
        "## Exports",
        "",
        "| Module | Name | Object |",
        "|---|---|---|",
    ]
    for row in tables["exports"]:
        module = plain_cell(row["module_id"])
        name = plain_cell(row["name"])
        lines.append(f"| {module} | {name} | `{row['object_hash']}` |")
    return root, ("\n".join(lines) + "\n").encode("utf-8")


def rejects(archive, diagnostic):
    try:
        render(archive)
    except ArchiveError as exc:
        if diagnostic not in str(exc):
            raise
    else:
        raise AssertionError(("invalid archive produced a projection", archive))


def corrupt_payload(prior, current):
    with ZipFile(prior) as before, ZipFile(current, "w") as after:
        for entry in before.infolist():
            data = before.read(entry)
            if entry.filename == f"objects/{H1.split(':', 1)[1]}":
                data = b"wrong"
            after.writestr(entry, data)


def record(work):
    standard = sample_index()
    changed = deepcopy(standard)
    changed["exports"][0]["object_hash"] = H2
    punctuated = deepcopy(standard)
    punctuated["exports"][0]["name"] = "display|literal`[x](<b>&)"
    variations = {
        "baseline": (standard, "fixture-package", "index"),
        "exact-rebuild": (standard, "fixture-package", "index"),
        "display-metadata-edit": (standard, "renamed-package", "index"),
        "machine-index-relocated": (standard, "fixture-package", "metadata/tables"),
        "changed-export-target": (normalize(changed), "fixture-package", "index"),
        "escaped-export-name": (normalize(punctuated), "fixture-package", "index"),
    }
    archives = {}
    documents = {}
    for label, (index, name, prefix) in variations.items():
        path = work / f"{label}.llpkg"
        static_archive(path, index, name, prefix)
        root, data = render(path)
        archives[label] = {"package_root": root, "archive_sha256": sha256(path.read_bytes()).hexdigest(),
                           "index_markdown_sha256": sha256(data).hexdigest()}
        documents[label] = data

    assert archives["baseline"] == archives["exact-rebuild"]
    for label in ("display-metadata-edit", "machine-index-relocated"):
        assert archives[label]["archive_sha256"] != archives["baseline"]["archive_sha256"]
        assert archives[label]["package_root"] == archives["baseline"]["package_root"]
        assert documents[label] == documents["baseline"]
    assert archives["changed-export-target"]["package_root"] != archives["baseline"]["package_root"]
    assert documents["changed-export-target"] != documents["baseline"]
    assert b"display&#124;literal&#96;&#91;x&#93;&#40;&lt;b&gt;&amp;&#41;" in documents["escaped-export-name"]

    base = work / "baseline.llpkg"
    advice = work / "INDEX.md"
    advice.write_bytes(documents["baseline"])
    correct = advice.read_bytes() == render(base)[1]
    advice.write_bytes(documents["baseline"].replace(b"| alpha |", b"| false-name |"))
    edited = advice.read_bytes() == render(base)[1]
    stale = documents["baseline"] == render(work / "changed-export-target.llpkg")[1]
    assert (correct, edited, stale) == (True, False, False)
    advice.unlink()
    assert verify_archive(base, max_records_in_memory=2)

    embedded = work / "embedded-extra.llpkg"
    shutil.copyfile(base, embedded)
    with ZipFile(embedded, "a") as archive:
        archive.writestr("INDEX.md", documents["baseline"])
    rejects(embedded, "unexpected entries")
    damaged = work / "bad-payload.llpkg"
    corrupt_payload(base, damaged)
    rejects(damaged, "Content Hash mismatch")

    paths = (HERE / "run.py", PACKAGE_INDEX / "package_archive.py", PACKAGE_INDEX / "test_package_archive.py",
             PACKAGE_INDEX / "package_index.py", PACKAGE_IDENTITY / "package_identity.py")
    return ({
        "archives": archives,
        "sidecar_checks": {"correct": correct, "edited": edited, "stale": stale, "absence_preserves_package": True},
        "strict_archive_controls": {"embedded_undeclared_index_refused": True, "changed_payload_refused": True},
        "source_sha256": {path.relative_to(HERE.parents[3]).as_posix(): sha256(path.read_bytes()).hexdigest()
                          for path in paths},
    }, documents["baseline"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--example", type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-static-index-") as temp:
        result, example = record(Path(temp))
    args.example.write_bytes(example)
    print(json.dumps(result, indent=2))
