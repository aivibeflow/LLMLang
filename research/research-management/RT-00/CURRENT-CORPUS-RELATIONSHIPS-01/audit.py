#!/usr/bin/env python3
"""Screen exact research/all Markdown for scoped relationship candidates."""
import argparse
from collections import Counter, defaultdict, deque
from hashlib import sha256
from io import BytesIO
from itertools import combinations
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import subprocess
from urllib.parse import unquote, urlsplit


BASE = "9847850c12cda140e0bdb396d611c2ec96b85c33"
CONTROLS = "research/research-management/RT-00/RT-00-B-13-KNOWN-RELATIONSHIP-CONTROLS-2026-11-25.json"
ROOTS = ("README.md", "PLAN.md", "TODO.md", "research/README.md")
INLINE = re.compile(r"!?\[[^\]\n]+\]\(\s*(?:<([^>\n]+)>|([^\s)]+))")
DEFINITION = re.compile(r"^\s{0,3}\[([^\]\n]+)\]:\s*(?:<([^>\n]+)>|([^\s]+))")
REFERENCE = re.compile(r"!?\[([^\]\n]+)\]\[([^\]\n]*)\]")
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
CUE = re.compile(r"supersed|obsolete|replaces?\b|contradict|companion|translation|historical|different scope|"
                 r"narrow(?:er|s) scope|linked revision|current guidance|version lineage", re.I)
MARKDOWN_SUFFIXES = (".md", ".mdx")
BASENAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*\.mdx?\b")
SCENARIO = re.compile(r"(?:scenario[ -]+)([0-9]+)\b", re.I)
SCENARIO_FILE = re.compile(r"^RESEARCH-SCENARIO-([0-9]+)-")


def git(root, *arguments, data=None):
    return subprocess.run(["git", *arguments], cwd=root, input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=True, timeout=20).stdout


def load_tree(root):
    tree = {}
    for field in git(root, "ls-tree", "-r", "-z", BASE).split(b"\0"):
        if not field:
            continue
        header, path = field.split(b"\t", 1)
        _, kind, oid = header.split()
        if kind == b"blob":
            tree[path.decode()] = oid.decode()
    docs = {path: oid for path, oid in tree.items() if path.lower().endswith(MARKDOWN_SUFFIXES)}
    requested = sorted(set(docs.values()) | {tree[CONTROLS]})
    batch = BytesIO(git(root, "cat-file", "--batch", data=("\n".join(requested) + "\n").encode()))
    contents = {}
    for oid in requested:
        given, kind, size = batch.readline().decode().split()
        assert given == oid and kind == "blob"
        contents[oid] = batch.read(int(size)).decode()
        assert batch.read(1) == b"\n"
    assert not batch.read()
    return docs, {path: contents[oid] for path, oid in docs.items()}, json.loads(contents[tree[CONTROLS]])


def blocks(text):
    result = []
    current = []
    opener = None
    for number, line in enumerate(text.splitlines(), 1):
        fence = FENCE.match(line)
        if fence:
            token = fence[1]
            if opener is None:
                if current:
                    result.append(current)
                    current = []
                opener = token
            elif token[0] == opener[0] and len(token) >= len(opener):
                opener = None
            continue
        if opener is not None or not line.strip():
            if current:
                result.append(current)
                current = []
            continue
        if line.lstrip().startswith(("|", "#", "- ", "* ", "> ", "+ ")):
            if current:
                result.append(current)
                current = []
            result.append([(number, line)])
        else:
            current.append((number, line))
    if current:
        result.append(current)
    return result


def link_target(source, value, docs):
    try:
        url = urlsplit(value)
    except ValueError:
        return None
    if url.scheme in ("https", "http") and url.netloc.casefold() == "github.com":
        prefix = "/aivibeflow/LLMLang/blob/"
        if url.path.casefold().startswith(prefix.casefold()):
            relative = url.path[len(prefix):]
            if relative.startswith("research/all/"):
                result = unquote(relative[len("research/all/"):])
            elif relative.startswith(BASE + "/"):
                result = unquote(relative[len(BASE) + 1:])
            else:
                return None
        else:
            return None
    elif not url.scheme and not url.netloc and url.path:
        path = unquote(url.path)
        result = posixpath.normpath(posixpath.join(posixpath.dirname(source), path))
    else:
        return None
    return result if result != source and result in docs else None


def references(rows):
    table = {}
    for _, text in rows:
        found = DEFINITION.match(text)
        if found:
            key, absolute, bare = found.groups()
            table.setdefault(key.casefold(), absolute or bare)
    return table


def targets(path, block, definitions, docs):
    named = set()
    for index, line in block:
        defined = DEFINITION.match(line)
        candidates = [root or plain for root, plain in INLINE.findall(line)]
        candidates.extend(definitions.get((key or label).casefold())
                          for label, key in REFERENCE.findall(line))
        if defined:
            continue
        resolved = (link_target(path, value, docs) for value in candidates if value)
        named.update(dest for dest in resolved if dest)
    return named


def normalized_paragraph(text):
    text = INLINE.sub(" ", text)
    text = re.sub(r"https?://\S+", " ", text)
    words = re.findall(r"[^\W_]+", text.casefold())
    if len(words) >= 24:
        return " ".join(words)
    return None


def controls(graph, candidates, docs, archive):
    result = []
    for item in archive["controls"]:
        paths = []
        for old_path, oid in zip(item["paths"], item["blobs"]):
            if docs.get(old_path) == oid:
                paths.append(old_path)
                continue
            aliases = [path for path, actual in docs.items() if actual == oid]
            assert len(aliases) == 1, (old_path, aliases)
            paths.append(aliases[0])
        first, second = sorted(paths)
        signals = candidates.get((first, second), {})
        outside_prior_review = any(
            mode == "shared_paragraph" or not entry[0].startswith("research/research-management/")
            for mode, entries in signals.items() for entry in entries
        )
        result.append({"pair": [first, second], "unchanged_blobs": sorted(item["blobs"]),
                       "recorded_relationship": item["relationship"],
                       "has_direct_reference": second in graph[first] or first in graph[second],
                       "candidate_outside_research_management": outside_prior_review,
                       "candidates": signals})
    return result


def verify_parsing():
    docs = {"research/source.md", "research/first.md", "research/second.md", "research/a b.md"}
    body = """[first](first.md#anchor) and [spaced](<a b.md>) in the same paragraph.
[reference][b].

[b]: second.md

~~~sh
[not prose](missing.md)
~~~
"""
    parsed = blocks(body)
    definitions = references([row for block in parsed for row in block])
    assert targets("research/source.md", parsed[0], definitions, docs) == docs - {"research/source.md"}
    assert len(parsed) == 2
    assert link_target("research/source.md", "../missing.md", docs) is None
    assert link_target("research/source.md", "https://github.com/aivibeflow/LLMLang/blob/main/research/first.md", docs) is None


def analyze(docs, contents, known):
    research = {path for path in docs if path.startswith("research/")}
    filenames = defaultdict(list)
    scenarios = defaultdict(list)
    for path in sorted(research):
        name = PurePosixPath(path).name
        filenames[name].append(path)
        match = SCENARIO_FILE.match(name)
        if match:
            scenarios[match[1]].append(path)

    def only_candidate(pool, key):
        matches = pool.get(key, [])
        return matches if len(matches) == 1 else []

    graph = defaultdict(set)
    paragraphs = defaultdict(dict)
    pairs = defaultdict(lambda: defaultdict(list))
    for path, content in contents.items():
        groups = blocks(content)
        refs = references([row for group in groups for row in group])
        for group in groups:
            outgoing = targets(path, group, refs, docs)
            graph[path].update(outgoing)
            if not path.startswith("research/"):
                continue
            prose = " ".join(line for _, line in group)
            if CUE.search(prose):
                reports = sorted(dest for dest in outgoing if dest.startswith("research/"))
                if len(reports) <= 4:
                    for report in reports:
                        pairs[tuple(sorted((path, report)))]["direct_cue"].append([path, group[0][0]])
                    for pair in combinations(reports, 2):
                        pairs[pair]["shared_citation"].append([path, group[0][0]])
                named = {dest for match in BASENAME.findall(prose)
                         for dest in only_candidate(filenames, match)}
                named.update(dest for match in SCENARIO.findall(prose)
                             for dest in only_candidate(scenarios, match))
                if 2 <= len(named) <= 4:
                    for pair in combinations(sorted(named - {path}), 2):
                        pairs[pair]["shared_literal_reference"].append([path, group[0][0]])
            value = normalized_paragraph(prose)
            if value and path not in paragraphs[value]:
                paragraphs[value][path] = group[0][0]
    for paragraph, sources in paragraphs.items():
        if not 2 <= len(sources) <= 6:
            continue
        for first, second in combinations(sorted(sources), 2):
            pairs[first, second]["shared_paragraph"].append({
                "sha256": sha256(paragraph.encode()).hexdigest(), "lines": [sources[first], sources[second]],
            })
    reachable = set(ROOTS)
    pending = deque(ROOTS)
    while pending:
        for dest in sorted(graph[pending.popleft()] - reachable):
            reachable.add(dest)
            pending.append(dest)
    incoming = Counter(dest for outgoing in graph.values() for dest in outgoing)
    for path in sorted(research):
        if not path.endswith(".ru.md"):
            continue
        companion = path.removesuffix(".ru.md") + ".md"
        if companion in graph[path] and path in graph[companion]:
            pairs[tuple(sorted((path, companion)))][
                "reciprocal_language_navigation"].append([path, companion])
    zero = sorted(path for path in research if not incoming[path])
    unindexed = sorted(research - reachable)
    mentions = defaultdict(list)
    for orphan in zero:
        unique_name = PurePosixPath(orphan).name
        if len(filenames[unique_name]) == 1:
            mentions[orphan] = [path for path, details in contents.items()
                                if path != orphan and unique_name in details]
    all_candidates = [{"first": first, "second": second,
                       "sources": {mode: sorted(items, key=lambda x: json.dumps(x, sort_keys=True))
                                   for mode, items in sources.items()}}
                      for (first, second), sources in sorted(pairs.items())]
    assert set(zero) <= set(unindexed) | set(ROOTS)
    groups = Counter(docs[path] for path in research)
    return {"research_markdown": len(research), "all_tracked_markdown": len(docs),
            "distinct_research_blobs": len(groups), "repeated_markdown_blob_groups":
                sum(count > 1 for count in groups.values()),
            "graph_roots": ROOTS, "zero_tracked_markdown_inbound": zero, "unreached_research": unindexed,
            "zero_inbound_with_literal_mention": {path: sorted(items) for path, items in mentions.items() if items},
            "known_controls": controls(graph, pairs, docs, known), "candidates": all_candidates,
            "candidate_counts": dict(Counter(mode for row in all_candidates for mode in row["sources"])),
            "source_blobs": {path: docs[path] for path in sorted(research)}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    directory = Path(git(Path.cwd(), "rev-parse", "--show-toplevel").decode().strip())
    verify_parsing()
    docs, contents, known = load_tree(directory)
    report = {"baseline": BASE, **analyze(docs, contents, known)}
    args.out.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
