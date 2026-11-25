"""Check the RT-03 outgoing coordinate crosswalk against its exact archive."""

from collections import Counter
from hashlib import sha256
import json
import posixpath
from pathlib import Path
import re
import subprocess


BASE = "5254e1a74ae4aff6d820e3b36c8a651e7dd59db4"
MAP = "research/research-management/RESEARCH-DEPENDENCY-MAP.md"
REPORT = "research/language-design/RT-03/RT-03-DOWNSTREAM-EDGE-EVIDENCE-2026-11-25.md"


def git(*args):
    return subprocess.check_output(("git", *args))


def run():
    raw_map = git("show", f"{BASE}:{MAP}")
    archived = re.findall(r"^\| (DEP-\d+) \| RT-03 → (RT-\d+) \|", raw_map.decode(), re.MULTILINE)
    assert len(archived) == len(dict(archived))
    report = (Path(__file__).resolve().parent.parent / Path(REPORT).name).read_bytes()
    entries = re.findall(r"^\| (DEP-\d+) \| (RT-\d+) \| \[(Scoped check|Proxy)\]\(([^)]+)\) \|",
                         report.decode(), re.MULTILINE)
    assert len(entries) == len(archived)
    assert dict(archived) == {edge: target for edge, target, _, _ in entries}
    records = {}
    for edge, target, status, link in entries:
        path = posixpath.normpath(posixpath.join(posixpath.dirname(REPORT), link))
        blob = git("rev-parse", f"{BASE}:{path}").decode().strip()
        assert git("cat-file", "-t", blob) == b"blob\n"
        records[edge] = {"target": target, "disposition": status, "report_path": path, "blob": blob}
    return {
        "baseline": BASE, "map_sha256": sha256(raw_map).hexdigest(),
        "report_sha256": sha256(report).hexdigest(), "outgoing_edges": len(archived),
        "dispositions": dict(Counter(record["disposition"] for record in records.values())),
        "entries": records,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
