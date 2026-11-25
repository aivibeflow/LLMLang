"""Measure current corpus navigation and preserve its exact path/blob inventory."""

import argparse
from collections import Counter
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

BASE = "877db318a2c63f51116b63714001b3e96640a4a9"
RESEARCH = "research/"
FIX = "research/runtime-and-systems/RT-10/RT-10-LINUX-SYSCALL-ABI-ISOLATION-2026-11-25.md"
OLD_LINK = "RT-10-POSIX-PPOLL-FFI-BOUNDARY-2026-11-25.md"
NEW_LINK = "RT-10-PPOLL-FFI-BOUNDARY-2026-11-25.md"


def git(*args):
    return subprocess.check_output(["git", *args])


def inventory():
    records = {}
    for item in git("ls-tree", "-r", "-l", "-z", BASE, "research").split(b"\0"):
        if item:
            meta, path = item.decode().split("\t", 1)
            _, kind, blob, size = meta.split()
            assert kind == "blob" and path.startswith(RESEARCH), path
            records[path] = (blob, int(size))
    return records


def navigate(archive):
    code = ("import json, sys; from pathlib import Path; "
            "from audit_research_index_reachability import measure; "
            "print(json.dumps(measure(Path(sys.argv[1])), sort_keys=True))")
    process = subprocess.check_output(
        [sys.executable, "-B", "-c", code, str(archive)],
        cwd=archive / ".github/scripts",
    )
    return json.loads(process)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    inventory_records = inventory()
    with tempfile.TemporaryDirectory(prefix="llmlang-corpus-synthesis-") as temporary:
        archive = Path(temporary)
        subprocess.run(["tar", "-x", "-C", temporary], input=git("archive", BASE), check=True)
        archived = {path.relative_to(archive).as_posix(): path.stat().st_size
                    for path in (archive / "research").rglob("*") if path.is_file()}
        assert archived == {path: size for path, (_, size) in inventory_records.items()}
        baseline = navigate(archive)
        source = archive / FIX
        content = source.read_text()
        assert content.count(OLD_LINK) == 1 and source.with_name(NEW_LINK).is_file()
        source.write_text(content.replace(OLD_LINK, NEW_LINK, 1))
        navigation = navigate(archive)
    summary = navigation["summary"]
    assert len(inventory_records) == summary["artifacts"]
    directory_needed = set(navigation["artifacts_reachable_only_with_directory_links"])
    unreachable = set(navigation["artifacts_unreachable_with_directory_links"])
    faults = navigation["unresolved_local_path_occurrences"]
    first_party = [row for row in faults if not row["source"].startswith(
        "research/references/snapshots/")]
    assert not first_party
    assert baseline["unresolved_local_path_occurrences"].count(
        {"source": FIX, "target": OLD_LINK}) == 1
    assert len(baseline["unresolved_local_path_occurrences"]) == len(faults) + 1
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(json.dumps({
        "baseline": BASE, "python": platform.python_version(),
        "git": git("--version").decode().strip(), "architecture": platform.machine(),
        "navigation": summary,
        "baseline_navigation": baseline["summary"],
        "repaired_first_party_citation": {"source": FIX, "from": OLD_LINK, "to": NEW_LINK},
        "unresolved_path_origins": dict(Counter(
            "copied_snapshot" if row not in first_party else "first_party" for row in faults)),
        "first_party_unresolved": first_party,
        "all_unresolved": faults,
    }, indent=2, sort_keys=True) + "\n")
    with (args.out / "artifacts.tsv").open("w", encoding="utf-8") as handle:
        handle.write("path\tgit_blob\tbytes\tnavigation\n")
        for path, (blob, size) in inventory_records.items():
            access = ("unreachable" if path in unreachable else
                      "directory" if path in directory_needed else "document")
            handle.write(f"{path}\t{blob}\t{size}\t{access}\n")


if __name__ == "__main__":
    main()
