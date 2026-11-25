"""Compare raw native Git diffs with a registered local textconv."""

import hashlib
import json
import platform
import shlex
import sys
import tempfile
from pathlib import Path

from project import VERSION, project

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "COMMIT-TREE-SEMANTIC-ROOT-01"))
from run import SOURCES, from_tree, git, make_commit, make_tree

BASELINE = "b42d1b0b8fd1332a49a0ee91c0ff7b19e7b6ac63"
SOURCE = "program.json"
METADATA = "review.json"
ATTRS = b"program.json diff=llmlang-review\n"


def metadata(root):
    return (json.dumps({"schema": VERSION, "root": root}, sort_keys=True) + "\n").encode()


def reconstruct(repo, tree):
    source = git(repo, "show", f"{tree}:{SOURCE}")
    subset = make_tree(repo, {SOURCE: source})
    root, values = from_tree(repo, subset)
    return {"root": root, "values": values}


def make_fixture(repo):
    git(repo, "init", "--quiet", "--initial-branch=research/all", "--object-format=sha1")
    original = SOURCES[SOURCE]
    source = json.loads(original)
    formatted = (json.dumps({"entry": source["entry"], "binding": source["binding"]}, indent=2)
                 + "\n").encode()
    changed = original.replace(b"plus", b"minus")
    root_a = reconstruct(repo, make_tree(repo, {SOURCE: original}))["root"]
    root_b = reconstruct(repo, make_tree(repo, {SOURCE: changed}))["root"]
    assert root_a != root_b
    definitions = [
        ("base", original, metadata(root_a), ATTRS),
        ("format", formatted, metadata(root_a), ATTRS),
        ("provider-fresh", changed, metadata(root_b), ATTRS),
        ("provider-stale", changed, metadata(root_a), ATTRS),
        ("metadata-only", original, metadata(root_b), ATTRS),
        ("missing-attributes", formatted, metadata(root_a), b""),
    ]
    commits = {}
    for name, data, receipt, attrs in definitions:
        files = {SOURCE: data, METADATA: receipt}
        if attrs:
            files[".gitattributes"] = attrs
        parents = (commits["base"],) if "base" in commits else ()
        commits[name] = make_commit(repo, make_tree(repo, files), name, *parents)
        git(repo, "update-ref", f"refs/tags/{name}", commits[name])
    git(repo, "update-ref", "refs/heads/research/all", commits["base"])
    return commits


def diff(repo, base, candidate, *options):
    return git(repo, "diff", "--no-color", "--no-ext-diff", "--no-renames",
               *options, base, candidate, "--", SOURCE).decode()


def compare(repo, name, base, candidate):
    native = diff(repo, base, candidate, "--no-textconv")
    clean = diff(repo, base, candidate, "--textconv")
    assert clean == native
    assert bool(native) == (name != "metadata-only")
    git(repo, "config", "diff.llmlang-review.textconv",
        shlex.join((sys.executable, "-B", str(HERE / "project.py"))))
    git(repo, "config", "diff.llmlang-review.cachetextconv", "false")
    rendered = diff(repo, base, candidate, "--textconv")
    git(repo, "config", "--remove-section", "diff.llmlang-review")
    assert diff(repo, base, candidate, "--textconv") == clean

    expected_source = git(repo, "show", f"{candidate}:{SOURCE}")
    expected_render = project(expected_source)
    before = reconstruct(repo, base)
    after = reconstruct(repo, candidate)
    root_changed = name.startswith("provider-")
    assert (after["root"] != before["root"]) == root_changed
    assert after["values"] == ([-2, -1, 0] if root_changed else [0, 1, 2])
    if root_changed:
        assert "-compute provider plus\n" in rendered and "+compute provider minus\n" in rendered
        assert expected_render.splitlines()[1] == "compute provider minus"
    elif name == "missing-attributes":
        assert rendered == native
    else:
        assert rendered == "" and expected_render == project(SOURCES[SOURCE])
    evidence_matches = git(repo, "show", f"{candidate}:{METADATA}") == metadata(after["root"])
    metadata_patch = git(repo, "diff", "--no-color", "--no-ext-diff", "--no-textconv",
                         base, candidate, "--", METADATA).decode()
    assert bool(metadata_patch) == (name in {"provider-fresh", "metadata-only"})
    assert evidence_matches == (name not in {"provider-stale", "metadata-only"})
    return {
        "candidate": candidate, "native_patch": native, "unconfigured_patch": clean,
        "configured_patch": rendered, "semantic_snapshot": after,
        "generated_metadata_matches": evidence_matches, "metadata_patch": metadata_patch,
    }


def main():
    with tempfile.TemporaryDirectory(prefix="llmlang-review-projection-") as temporary:
        directory = Path(temporary)
        origin = directory / "origin"
        origin.mkdir()
        commits = make_fixture(origin)
        examples = {}
        for name, candidate in commits.items():
            if name == "base":
                continue
            clone = directory / name
            git(directory, "clone", "--quiet", origin.as_uri(), str(clone))
            git(clone, "switch", "--quiet", "--detach", candidate)
            examples[name] = compare(clone, name, commits["base"], candidate)
    helper = HERE.parent / "COMMIT-TREE-SEMANTIC-ROOT-01" / "run.py"
    sources = [helper, *(
        ROOT / "research/PROTOTYPES/DEPENDENCY-GRAPH-01/src" / name
        for name in ("spg_admission.py", "spg_representation.py", "semantic_graph.py",
                     "recursive_identity.py")
    )]
    pins = {}
    for source in sources:
        relative = str(source.relative_to(ROOT))
        archived = git(ROOT, "show", f"{BASELINE}:{relative}")
        assert archived == source.read_bytes(), relative
        pins[relative] = hashlib.sha256(archived).hexdigest()
    print(json.dumps({
        "baseline": BASELINE, "git": git(ROOT, "--version").decode().strip(),
        "python": platform.python_version(), "schema": VERSION, "base_commit": commits["base"],
        "study_sha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                         for name in ("run.py", "project.py")},
        "source_sha256": pins, "examples": examples,
    }, indent=2))


if __name__ == "__main__":
    main()
