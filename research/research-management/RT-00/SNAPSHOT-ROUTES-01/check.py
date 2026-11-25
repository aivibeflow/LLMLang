"""Resolve copied-document link failures against manifest-pinned upstream trees."""

import argparse
from collections import Counter
import json
from pathlib import Path
import posixpath
import re
import subprocess
from urllib.parse import unquote, urlsplit

BASE = "877db318a2c63f51116b63714001b3e96640a4a9"
MANIFEST = "research/references/SNAPSHOT-MANIFEST.json"
NAV = Path(__file__).resolve().parent.parent / "NAVIGATION-DELTA-01/evidence.json"
FOLDERS = {"modelcontextprotocol/modelcontextprotocol": "mcp",
           "opencontainers/image-spec": "oci", "AliveToolkit/alive2": "alive2"}
ANCHOR = re.compile(r"""\b(?:id|name)\s*=\s*["']([^"']+)["']""")


def git(*args, repo=None):
    command = ["git"] if repo is None else ["git", "-C", str(repo)]
    return subprocess.check_output([*command, *args])


def blob(revision, path, repo=None):
    return git("show", f"{revision}:{path}", repo=repo)


def anchors(text):
    found = set(ANCHOR.findall(text))
    fenced = False
    counts = Counter()
    for line in text.splitlines():
        if line.lstrip().startswith(("~~~", chr(96) * 3)):
            fenced = not fenced
            continue
        if fenced:
            continue
        heading = re.match(r"^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
        if heading:
            value = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", heading[1])
            value = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"\1", value)
            value = re.sub(r"[^\w -]", "", value.lower()).replace(" ", "-")
            count = counts[value]
            found.add(value if count == 0 else f"{value}-{count}")
            counts[value] += 1
    return found


def target_path(group, source, route, upstream_tree):
    if group == "mcp":
        name = "docs" + route
        candidates = (name + ".mdx", name + "/index.mdx", name)
    else:
        candidates = (posixpath.normpath(posixpath.join(posixpath.dirname(source), route)),)
    matches = [path for path in candidates if path in upstream_tree]
    assert len(matches) <= 1, (group, source, route, matches)
    return matches[0] if matches else None


def load_upstream(repo, entry):
    rev = entry["commit"]
    assert git("rev-parse", f"{rev}^{{tree}}", repo=repo).decode().strip() == entry["tree_sha"]
    tree = {}
    for row in git("ls-tree", "-rz", rev, repo=repo).split(b"\0"):
        if row:
            metadata, path = row.decode().split("\t", 1)
            _, kind, oid = metadata.split()
            if kind == "blob":
                tree[path] = oid
    for item in entry["files"]:
        assert tree[item["source"]] == item["upstream_blob_sha"]
        local = git("rev-parse", f"{BASE}:{item['local']}").decode().strip()
        assert local == item["upstream_blob_sha"], item
    return tree


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for folder in FOLDERS.values():
        parser.add_argument(f"--{folder}", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(blob(BASE, MANIFEST))
    sources = {item["local"]: (entry, item) for entry in manifest["sources"]
               if entry["repository"] in FOLDERS for item in entry["files"]}
    trees = {folder: load_upstream(getattr(args, folder), entry)
             for entry in manifest["sources"]
             if (folder := FOLDERS.get(entry["repository"]))}
    occurrences = json.loads(NAV.read_bytes())["after_link_repair"]["lychee_errors"]
    assert len(occurrences) == 82
    result = []
    anchor_cache = {}
    for occurrence in occurrences:
        local, link = occurrence["source"], occurrence["url"]
        entry, item = sources[local]
        group = FOLDERS[entry["repository"]]
        parts = urlsplit(link)
        assert parts.scheme == "file" and parts.path.startswith("/input/")
        route = unquote(parts.path.removeprefix("/input"))
        if group != "mcp":
            route = posixpath.relpath(route.removeprefix("/"), posixpath.dirname(local))
        path = target_path(group, item["source"], route, trees[group])
        fragment = unquote(parts.fragment)
        alternate = None
        disposition = "no_source_path"
        if path is not None:
            if not fragment:
                disposition = "path"
            else:
                key = (group, path)
                if key not in anchor_cache:
                    anchor_cache[key] = anchors(blob(entry["commit"], path, getattr(args, group)).decode())
                available_anchors = anchor_cache[key]
                disposition = "fragment" if fragment in available_anchors else "fragment_unverified"
                if disposition == "fragment_unverified" and "_" + fragment in available_anchors:
                    alternate = "_" + fragment
        available = next((row["local"] for row in entry["files"] if row["source"] == path), None)
        result.append({
            **occurrence, "group": group, "upstream_commit": entry["commit"],
            "source_blob": item["upstream_blob_sha"], "upstream_path": path,
            "destination_blob": trees[group].get(path), "existing_local_copy": available,
            "disposition": disposition,
            **({"available_heading_id": alternate} if alternate else {}),
        })
    print(json.dumps({
        "base": BASE,
        "group_counts": dict(Counter(row["group"] for row in result)),
        "dispositions": dict(Counter(row["disposition"] for row in result)),
        "distinct_source_targets": len({(row["group"], row["upstream_path"]) for row in result}),
        "routes_to_existing_local_copies": sum(row["existing_local_copy"] is not None for row in result),
        "input_scan_blob": subprocess.check_output(["git", "hash-object", str(NAV)]).decode().strip(),
        "source_files_verified": len(sources), "occurrences": result,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
