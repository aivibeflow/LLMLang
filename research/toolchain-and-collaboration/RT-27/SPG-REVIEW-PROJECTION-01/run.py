#!/usr/bin/env python3
"""Check review text and exact derived metadata against recovered SPG graphs."""

from contextlib import contextmanager
import json
from pathlib import Path
import runpy
import sys
from tempfile import TemporaryDirectory

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
BASE = runpy.run_path(str(HERE.parent / "SPG-PROFILED-RECORDS-01/run.py"))
git = BASE["git"]
canonical_bytes = BASE["canonical_bytes"]
digest = BASE["digest"]
serialize = BASE["serialize"]
load = BASE["load"]
checked_graph = BASE["checked_graph"]
Graph = BASE["Graph"]


class Refusal(ValueError):
    pass


@contextmanager
def layout(buckets):
    module = serialize.__globals__
    original = module["BUCKETS"], module["PROFILE"]
    module["BUCKETS"], module["PROFILE"] = buckets, f"fixture-review-carrier/{buckets}"
    try:
        yield
    finally:
        module["BUCKETS"], module["PROFILE"] = original


def render(graph):
    lines = ["Typed SPG review projection", f"Semantic root {graph.snapshot.root_hash}"]
    slots = graph.snapshot.mapping
    for slot, address in sorted(slots.items()):
        role, label = slot.split(":", 1)
        if role == "binding":
            edges = graph.store.get(address).dependencies
            provider, = [edge.target_hash for edge in edges if edge.relation == "implementation"]
            descriptions = sorted(name.split(":", 1)[1] for name, target in slots.items()
                                  if name.startswith("implementation:") and target == provider)
            assert descriptions
            lines.append(f"Binding {label} uses {', '.join(descriptions)} ({provider})")
        else:
            lines.append(f"{role.title()} {label} {address}")
    return ("\n".join(lines) + "\n").encode()


def receipt(root, text):
    return canonical_bytes({"semantic_root": root, "profile": "typed-spg-review/1", "sha256": digest(text)})


def publication(graph, relations, buckets):
    with layout(buckets):
        files = serialize(graph, relations, 2)
    review = render(graph)
    return files | {"review.txt": review, "review.json": receipt(graph.snapshot.root_hash, review)}


def admit_review(graph, text, claimed):
    if claimed != receipt(graph.snapshot.root_hash, text):
        raise Refusal("wrong review receipt scope or digest")
    if render(graph) != text:
        raise Refusal("review differs from exact restored SPG")
    return digest(text)


def commit(repo, files, prior, case):
    for name in prior - set(files):
        (repo / name).unlink()
    for name, raw in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    git(repo, "add", "-A")
    git(repo, "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", case)
    return git(repo, "rev-parse", "HEAD").decode().strip()


def changed_files(repo, before, after, *paths):
    return git(repo, "diff", "--no-ext-diff", "--name-only", before, after, "--", *paths).decode().splitlines()


def experiment(root):
    (base, base_rel, _), (changed, changed_rel, _) = BASE["fixtures"]()
    first = publication(base, base_rel, 4)
    repacked = publication(base, base_rel, 2)
    revised = publication(changed, changed_rel, 2)
    assert first["review.txt"] == repacked["review.txt"] and first["review.json"] == repacked["review.json"]
    assert revised["review.txt"] != repacked["review.txt"]
    wrong_text = revised["review.txt"].replace(b"uses alternate", b"uses primary")
    assert wrong_text != revised["review.txt"]
    wrong_provenance = revised | {"review.json": repacked["review.json"]}
    consistent_forgery = revised | {"review.txt": wrong_text,
                                   "review.json": receipt(changed.snapshot.root_hash, wrong_text)}
    fixtures = (
        ("base", first, 4, None),
        ("repacked", repacked, 2, None),
        ("rebound", revised, 2, None),
        ("stale-metadata", wrong_provenance, 2, "wrong review receipt scope or digest"),
        ("internally-consistent-stale-review", consistent_forgery, 2, "review differs from exact restored SPG"),
    )

    repo = root / "origin"
    repo.mkdir()
    git(repo, "init", "--quiet", "-b", "research/all", "--object-format=sha256")
    commits = {}
    previous = set()
    for name, files, _, _ in fixtures:
        commits[name] = commit(repo, files, previous, name)
        previous = set(files)
    clone = root / "read"
    git(root, "clone", "--quiet", "--no-local", str(repo), str(clone))
    git(clone, "fsck", "--full")
    git(clone, "remote", "remove", "origin")
    repo.rename(root / "source-unavailable")

    rows = []
    for name, _, buckets, refused in fixtures:
        pin = commits[name]
        git(clone, "checkout", "--quiet", "--detach", pin)
        with layout(buckets):
            store, _, snapshot, _ = checked_graph(load(clone, pin, {}))
        graph = Graph(store, snapshot)
        text = git(clone, "show", f"{pin}:review.txt")
        claimed = git(clone, "show", f"{pin}:review.json")
        try:
            address = admit_review(graph, text, claimed)
        except Refusal as error:
            assert refused == str(error)
            review = str(error)
        else:
            assert refused is None
            review = address
        rows.append({"case": name, "pin": pin, "semantic_root": snapshot.root_hash, "review": review})

    raw_repack = changed_files(clone, commits["base"], commits["repacked"])
    review_repack = changed_files(clone, commits["base"], commits["repacked"], "review.txt")
    semantic_change = changed_files(clone, commits["repacked"], commits["rebound"], "review.txt")
    assert raw_repack and review_repack == [] and semantic_change == ["review.txt"]
    diff = git(clone, "diff", "--no-ext-diff", commits["repacked"], commits["rebound"],
               "--", "review.txt").decode()
    assert "-Binding provider uses primary" in diff and "+Binding provider uses alternate" in diff
    return {
        "format": "spg-review-projection-01", "git": git(root, "--version").decode().strip(),
        "repacked_file_names": raw_repack, "repacked_review_changes": len(review_repack),
        "binding_diff": [line for line in diff.splitlines() if line.startswith(("-Binding", "+Binding"))],
        "rows": rows,
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-review-projection-") as work:
        evidence = experiment(Path(work))
    text = json.dumps(evidence, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
