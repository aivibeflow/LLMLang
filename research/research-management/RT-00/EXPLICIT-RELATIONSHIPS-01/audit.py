"""Screen direct research-document relationships named on the same line as a link."""

import argparse
import json
from pathlib import Path
import posixpath
import re
import subprocess
from urllib.parse import unquote

LINK = re.compile(r"\[([^\[\]]+)\]\(([^\s)]+)\)")
TRANSLATION_LABELS = {"english version", "русская версия"}
SUPERSESSION = re.compile(r"\bsupersed(?:e|es|ed|ing)\b|historical/background research", re.I)


def git(*args):
    return subprocess.check_output(["git", *args], text=True)


def inventory(revision):
    for record in git("ls-tree", "-rz", "--full-tree", revision, "--", "research").split("\0"):
        if record:
            metadata, path = record.split("\t", 1)
            _, kind, oid = metadata.split()
            if kind == "blob" and path.lower().endswith((".md", ".mdx")):
                yield path, oid


def collect(revision, paths):
    direct_pairs = set()
    candidates = []
    for source, source_blob in paths.items():
        document = git("show", f"{revision}:{source}")
        for line_number, line in enumerate(document.splitlines(), 1):
            for label, destination in LINK.findall(line):
                path = unquote(destination.split("#", 1)[0])
                if not path or path.startswith("/") or ":" in path:
                    continue
                target = posixpath.normpath(posixpath.join(posixpath.dirname(source), path))
                if target == source or target not in paths:
                    continue
                direct_pairs.add(tuple(sorted((source, target))))
                if label.casefold().strip() in TRANSLATION_LABELS:
                    signal = "translation-label"
                elif SUPERSESSION.search(line):
                    signal = "same-line-supersession-cue"
                else:
                    continue
                candidates.append({
                    "source": source,
                    "source_blob": source_blob,
                    "line": line_number,
                    "target": target,
                    "target_blob": paths[target],
                    "signal": signal,
                })
    return direct_pairs, candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("revision")
    parser.add_argument("--controls", required=True, help="B12 ledger path at the selected revision")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    revision = git("rev-parse", args.revision).strip()
    paths = dict(inventory(revision))
    direct_pairs, candidates = collect(revision, paths)
    candidate_pairs = {tuple(sorted((row["source"], row["target"]))) for row in candidates}
    controls = json.loads(git("show", f"{revision}:{args.controls}"))["known_relationship_controls"]
    control_results = []
    for row in controls:
        pair = tuple(sorted(row["paths"]))
        assert [paths[path] for path in row["paths"]] == row["blobs"], pair
        control_results.append({
            "paths": row["paths"],
            "blobs": row["blobs"],
            "b12_text_overlap_selected": row["candidate_selected"],
            "any_direct_link": pair in direct_pairs,
            "cue_selected": pair in candidate_pairs,
        })

    result = {
        "schema": "llmlang-rt00-explicit-relationship-screen/1",
        "revision": revision,
        "controls_blob": git("rev-parse", f"{revision}:{args.controls}").strip(),
        "markdown_documents": len(paths),
        "direct_link_pairs": len(direct_pairs),
        "candidate_pairs": len(candidate_pairs),
        "candidates": candidates,
        "controls": control_results,
    }
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
