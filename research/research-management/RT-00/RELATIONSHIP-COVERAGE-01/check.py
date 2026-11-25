"""Refresh corpus relationship coverage and bind each disposition to exact blobs."""

from collections import Counter, defaultdict
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import re
import subprocess

AREA = Path(__file__).resolve().parent.parent
SCREEN = AREA / "CURRENT-CORPUS-RELATIONSHIPS-01"
CUE_REVIEW = AREA / "RELATIONSHIP-CUE-ADJUDICATION-01/evidence.json"
BASE = "5f1d60b9daa25805dc008d1afeb0cf9efe4a9f91"
NEW_REVIEW = {
    "historical_scope_or_new_replay": {1, 2, 8, 9, 10, 11, 12, 13, 20, 23, 24, 26, 27, 28},
    "downstream_composition_or_distinct_profiles": {4, 5, 14, 21, 22, 29, 31},
    "navigation_or_crosswalk": {3, 6, 7, 15, 16, 17, 18, 19, 25, 30},
}
NAV = "research/references/README.md"
RECHECKED_CANDIDATES = {84, 92, 323, 385, 400, 403, 429, 434, 440}


def pair(row):
    return row["first"], row["second"]


def read_json(path):
    return json.loads(path.read_bytes())


def import_screen():
    spec = spec_from_file_location("corpus_relationship_screen", SCREEN / "audit.py")
    assert spec and spec.loader
    screen = module_from_spec(spec)
    spec.loader.exec_module(screen)
    screen.BASE = BASE
    return screen


def duplicates(contents, docs):
    titles, digests = defaultdict(list), defaultdict(list)
    for path, content in contents.items():
        if not path.startswith("research/"):
            continue
        title = re.search(r"(?m)^# (.+)$", content)
        if title:
            titles[title[1].casefold()].append(path)
        words = re.findall(r"[^\W_]+", content.casefold())
        if len(words) >= 40:
            digests[sha256(" ".join(words).encode()).hexdigest()].append(path)
    return {
        "repeated_titles": {
            title: [{"path": path, "blob": docs[path]} for path in paths]
            for title, paths in titles.items() if len(paths) > 1
        },
        "normalized_body_duplicates": {
            digest: paths for digest, paths in digests.items() if len(paths) > 1
        },
        "normalized_body_count": sum(map(len, digests.values())),
    }


def validate_rechecked_markers(strong, old_base, contents):
    for marker in strong["markers"]:
        spec = f"{old_base}:{marker['path']}"
        old_lines = subprocess.check_output(["git", "show", spec], text=True).splitlines()
        old_line = old_lines[marker["line"] - 1]
        assert sha256(old_line.encode()).hexdigest() == marker["excerpt_sha256"]
        assert contents[marker["path"]].splitlines().count(old_line) == 1, marker


def classify(row, original, strong, current, new_id, old_base, contents):
    paths = pair(row)
    if original is None:
        labels = [label for label, ids in NEW_REVIEW.items() if new_id in ids]
        assert len(labels) == 1
        return labels[0], None
    if strong:
        identities = [strong["first_blob"], strong["second_blob"]]
        assert current, paths
        live = [current["source_blobs"][path] for path in paths]
        if live != identities:
            assert strong["candidate"] in RECHECKED_CANDIDATES
            assert sum(a == b for a, b in zip(live, identities)) == 1
            validate_rechecked_markers(strong, old_base, contents)
            return strong["disposition"], strong["candidate"]
        assert strong["candidate"] not in RECHECKED_CANDIDATES
        return strong["disposition"], None
    sources = row["sources"]
    if "reciprocal_language_navigation" in sources:
        return "reciprocal_language_companion", None
    if "shared_paragraph" in sources:
        return "scoped_shared_paragraph", None
    if "direct_cue" in sources:
        return "direct_context_signal", None
    return "shared_context_signal", None


def main():
    root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
    screen = import_screen()
    screen.verify_parsing()
    docs, contents, controls = screen.load_tree(root)
    recent = screen.analyze(docs, contents, controls)
    old = read_json(SCREEN / "evidence.json")
    reviewed = read_json(CUE_REVIEW)
    direct_review = {pair(row): row for row in reviewed["reviewed"]}
    older = {pair(row): row for row in old["candidates"]}
    latest = {pair(row): row for row in recent["candidates"]}
    new = {key: number for number, key in enumerate(sorted(latest.keys() - older.keys()), 1)}
    assert set(new.values()) == set.union(*NEW_REVIEW.values())

    records = []
    for key in sorted(older.keys() | latest.keys()):
        row = latest.get(key, older.get(key))
        original = older.get(key)
        disposition, rechecked = classify(
            row, original, direct_review.get(key), recent if key in latest else None,
            new.get(key), old["baseline"], contents,
        )
        records.append({
            "paths": key, "blobs": [docs.get(path) for path in key],
            "signals": sorted(row["sources"]),
            "disposition": disposition, "present_in_current_screen": key in latest,
            **({"rechecked_prior_candidate": rechecked} if rechecked else {}),
        })
    assert {row["rechecked_prior_candidate"] for row in records
            if "rechecked_prior_candidate" in row} == RECHECKED_CANDIDATES
    snapshot_docs = recent["unreached_research"]
    assert all(path.startswith("research/references/snapshots/") for path in snapshot_docs)
    assert all(Path(path).name in contents[NAV] for path in snapshot_docs)
    print(json.dumps({
        "base": BASE, "old_base": old["baseline"], "prior_candidates": len(older),
        "current_candidates": len(latest), "new_candidates": len(new),
        "prior_candidates_absent_in_current_screen": len(older.keys() - latest.keys()),
        "current_document_count": recent["research_markdown"],
        "changed_endpoint_cue_rechecks": len(RECHECKED_CANDIDATES),
        "repeated_markdown_blob_groups": recent["repeated_markdown_blob_groups"],
        "duplicate_checks": duplicates(contents, docs),
        "snapshot_catalog_paths": snapshot_docs,
        "dispositions": dict(Counter(row["disposition"] for row in records)),
    }, sort_keys=True))
    for row in records:
        print(json.dumps(row, sort_keys=True))


if __name__ == "__main__":
    main()
