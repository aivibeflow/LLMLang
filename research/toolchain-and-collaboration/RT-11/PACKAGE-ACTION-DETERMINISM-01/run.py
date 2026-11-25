"""Compare deterministic archive bytes, package observations, and ordered writes."""

from hashlib import sha256
from itertools import combinations, product
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import zipfile

BASE = "d4e0ba59695dfdd9e43f1227cab75c4940b0bb39"
PROTOTYPES = "research/packages-and-ecosystem/PROTOTYPES"
INDEX = f"{PROTOTYPES}/PACKAGE-INDEX-01"
IDENTITY = f"{PROTOTYPES}/PACKAGE-IDENTITY-01"
INPUTS = (
    f"{INDEX}/package_archive.py", f"{INDEX}/package_index.py",
    f"{IDENTITY}/package_identity.py", f"{INDEX}/test_package_archive.py",
)
ORDERS = (
    ("register", "activate"), ("activate", "register"),
    ("register", "activate", "activate"), ("register", "activate"),
)


def digest(data):
    return sha256(data).hexdigest()


def export(temporary):
    archive = subprocess.check_output(["git", "archive", BASE, INDEX, IDENTITY])
    subprocess.run(["tar", "-x", "-C", str(temporary)], check=True, input=archive)
    sys.path[:0] = [str(temporary / INDEX), str(temporary / IDENTITY)]


def rewrite(source, target, date, reverse, corrupt=False):
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(target, "w") as output:
        names = original.namelist()
        if reverse:
            names.reverse()
        for name in names:
            data = original.read(name)
            if corrupt and name.startswith("objects/"):
                data = b"X" + data[1:]
            entry = zipfile.ZipInfo(name, date_time=date)
            output.writestr(entry, data)


def observation(path):
    from package_archive import verify_archive
    from package_identity import parse_manifest

    assert verify_archive(path, max_records_in_memory=1)
    with zipfile.ZipFile(path) as archive:
        manifest = parse_manifest(archive.read("manifest.toml"))
        contents = {name: digest(archive.read(name)) for name in sorted(archive.namelist())}
    return {
        "content_root": manifest["content"]["content_root"],
        "logical_index": manifest["index"]["logical_hash"],
        "expanded_entry_digests": contents,
    }


def compare_archives(temporary):
    from package_archive import ArchiveError, build_archive, verify_archive
    from test_package_archive import StreamingArchiveTests, payloads, sample_index, streams

    index = sample_index()
    manifest = StreamingArchiveTests().make_manifest(index)
    work = temporary / "artifacts"
    work.mkdir()
    canonical = []
    for run, cap in product(range(2), (1, 2, 4)):
        stage = work / f"canonical-{run}-{cap}"
        stage.mkdir()
        artifact = stage / "sample.llpkg"
        build_archive(manifest, streams(index), payloads(), artifact, max_records_in_memory=cap)
        canonical.append(artifact)

    exact = {digest(path.read_bytes()) for path in canonical}
    assert len(exact) == 1
    expected = observation(canonical[0])
    assert all(observation(path) == expected for path in canonical)
    carriers = []
    for year, reverse in product((2000, 2020), (False, True)):
        path = work / f"carrier-{year}-{reverse}.llpkg"
        rewrite(canonical[0], path, (year, 1, 1, 0, 0, 0), reverse)
        assert observation(path) == expected
        carriers.append({"timestamp_year": year, "reversed_entries": reverse,
                         "artifact": digest(path.read_bytes())})
    assert len({row["artifact"] for row in carriers} | exact) == 5
    corrupt = work / "invalid.llpkg"
    rewrite(canonical[0], corrupt, (2000, 1, 1, 0, 0, 0), False, corrupt=True)
    try:
        verify_archive(corrupt)
    except ArchiveError as error:
        assert "Payload" in str(error) or "Content Hash mismatch" in str(error)
    else:
        raise AssertionError("a corrupt object payload was admitted")

    return {"canonical_runs": len(canonical), "canonical_hash": exact.pop(),
            "alternate_carriers": carriers, "projected_observation": expected,
            "invalid_object_refused": True}


def append_events(path, calls, cache_by_artifact):
    receipts = []
    seen_artifacts = set()
    path.write_text("")
    for artifact, order in calls:
        cache_hit = cache_by_artifact and artifact in seen_artifacts
        seen_artifacts.add(artifact)
        if not cache_hit:
            with path.open("a", encoding="utf-8") as stream:
                for event in order:
                    stream.write(json.dumps({"artifact": artifact, "event": event}) + "\n")
        receipts.append({"status": "ok", "artifact": artifact, "executed": not cache_hit})
    return receipts, [json.loads(line) for line in path.read_text().splitlines()]


def compare_append(temporary, artifact):
    calls = [(artifact, order) for order in ORDERS]
    required, recorded = append_events(temporary / "required.jsonl", calls, False)
    projected, collapsed = append_events(temporary / "collapsed.jsonl", calls, True)
    assert sum(row["executed"] for row in required) == 4
    assert sum(row["executed"] for row in projected) == 1
    assert [row["event"] for row in recorded] == [event for order in ORDERS for event in order]
    assert [row["event"] for row in collapsed] == list(ORDERS[0])
    assert {row["event"] for row in recorded} == {row["event"] for row in collapsed}
    unequal_order = sum(left != right for left, right in combinations(ORDERS, 2))
    assert unequal_order == 5
    return {
        "requests": len(calls), "schedule_pairs_sharing_event_set": 6,
        "schedule_pairs_with_unequal_order_or_multiplicity": unequal_order,
        "exact_required_execution_receipts": required,
        "artifact_only_execution_receipts": projected,
        "exact_required_events": recorded, "artifact_only_events": collapsed,
    }


def main():
    with tempfile.TemporaryDirectory(prefix="llmlang-package-determinism-") as temporary:
        work = Path(temporary)
        export(work)
        exact = compare_archives(work)
        effect = compare_append(work, exact["canonical_hash"])
        inputs = {path: digest((work / path).read_bytes()) for path in INPUTS}
    print(json.dumps({
        "base": BASE, "python": platform.python_version(),
        "system": [platform.system(), platform.release(), platform.machine()],
        "inputs_sha256": inputs, "archives": exact, "ordered_append": effect,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
