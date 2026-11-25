"""Coordinate independently versioned interface mapping and Git branch updates."""
import argparse
from dataclasses import asdict, dataclass
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
GRAPH = HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"
COORDINATOR = HERE.parent / "GIT-CORE-COORDINATOR-01" / "run.py"
sys.path.insert(0, str(GRAPH))
from src.semantic_graph import canonical_bytes
from tests import test_rt23_interface_mapping_merge as mapping
from tests.test_candidate_graph_audit import declaration
from tests.test_rt23_mapping_tree_publication import export_mapping
from tests.test_rt24_merge_tree_gate import import_closed, read_inventory

spec = spec_from_file_location("fixture_mapping_git", COORDINATOR)
native = module_from_spec(spec)
sys.modules[spec.name] = native
spec.loader.exec_module(native)
GIT, HEAD, LOOKUP = native.GIT, native.HEAD, native.native.lookup
PREFIX = "refs/llmlang/research/all/interface/"
CURRENT, INCOMING, CATALOG = (PREFIX + part for part in ("current", "incoming", "catalog"))
MAPPING_FILE = "interface-mapping.json"
ORDINARY_FILE = "review.txt"
KEY = ("api", "entry")


@dataclass(frozen=True)
class Capture:
    head: str
    ours: str
    theirs: str
    catalog: str


def blob(repo, data):
    return GIT(repo, "hash-object", "-w", "--stdin", payload=canonical_bytes(data).decode() + "\n")


def read_revision(repo, address):
    raw = json.loads(GIT(repo, "cat-file", "blob", address))
    edits = tuple((tuple(key), tuple(value) if value is not None else None)
                  for key, value in raw["edits"])
    entries = tuple((tuple(key), tuple(value)) for key, value in raw["entries"])
    revision = mapping.Revision(tuple(raw["parents"]), edits, entries)
    assert raw["identity"] == revision.identity
    return revision


def write_revision(repo, revision):
    return blob(repo, {**asdict(revision), "identity": revision.identity})


def read_catalog(repo, address):
    raw = json.loads(GIT(repo, "cat-file", "blob", address))
    catalog = mapping.Catalog(raw["semantic_root"],
                              tuple((tuple(key), value) for key, value in raw["signatures"]))
    assert raw["identity"] == catalog.identity
    return catalog


def write_catalog(repo, catalog):
    return blob(repo, {**asdict(catalog), "identity": catalog.identity})


def capture(repo):
    return Capture(*(LOOKUP(repo, item) for item in (HEAD, CURRENT, INCOMING, CATALOG)))


def replace_blob(root, repo, path, address):
    rows = GIT(repo, "ls-tree", "-z", root).split("\0")
    unchanged = [row for row in rows if row and row.split("\t", 1)[1] != path]
    return GIT(repo, "mktree", "-z", payload="\0".join(
        [*unchanged, f"100644 blob {address}\t{path}", ""]
    ))


def join(repo, base_oid, expected, hook=lambda: None):
    if capture(repo) != expected:
        return {"status": "stale-before-prepare"}
    base = read_revision(repo, base_oid)
    ours = read_revision(repo, expected.ours)
    theirs = read_revision(repo, expected.theirs)
    catalog = read_catalog(repo, expected.catalog)
    inventory = read_inventory(repo, expected.head)
    _, semantic = import_closed(inventory)
    if semantic.root_hash != catalog.semantic_root:
        return {"status": "catalog-snapshot-mismatch"}
    try:
        candidate = mapping.prepare(base, ours, theirs, catalog)
    except mapping.MappingConflict as err:
        return {"status": "mapping-conflict", "detail": str(err)}

    revision_oid = write_revision(repo, candidate.revision)
    artifact = export_mapping(catalog, candidate).decode()
    artifact_oid = GIT(repo, "hash-object", "-w", "--stdin", payload=artifact)
    result_tree = replace_blob(expected.head, repo, MAPPING_FILE, artifact_oid)
    _, reopened = import_closed(read_inventory(repo, result_tree))
    assert reopened == semantic and read_revision(repo, revision_oid) == candidate.revision
    assert GIT(repo, "rev-parse", f"{result_tree}:{MAPPING_FILE}") == artifact_oid
    result = native.object_commit(repo, result_tree, "exact interface mapping " + candidate.identity,
                                  (expected.head,))
    hook()
    transition = GIT(repo, "update-ref", "--stdin", check=False, payload=(
        f"start\nverify {INCOMING} {expected.theirs}\nverify {CATALOG} {expected.catalog}\n"
        f"update {CURRENT} {revision_oid} {expected.ours}\nupdate {HEAD} {result} {expected.head}\n"
        "prepare\ncommit\n"
    ))
    if transition.returncode:
        return {"status": "ref-transaction-refused"}
    return {"status": "published", "commit": result, "tree": result_tree,
            "candidate": candidate.identity, "mapping_revision": candidate.revision.identity,
            "semantic_root": semantic.root_hash, "entries": candidate.revision.entries}


def inputs(scenario, base):
    edits = {KEY: ("g", "sig2")}, {("cli", "entry"): ("g", "cli-g")}
    if scenario == "same-key":
        edits = {KEY: ("g", "sig2")}, {KEY: ("g", "sig2")}
    elif scenario == "same-key-divergent":
        edits = {KEY: ("g", "sig2")}, {KEY: ("f", "sig1")}
    elif scenario == "delete-update":
        edits = {KEY: None}, {KEY: ("g", "sig2")}
    elif scenario == "export-collision":
        edits = {("api", "first"): ("g", "sig2")}, {("api", "second"): ("g", "sig2")}
    elif scenario == "wrong-signature":
        edits = {KEY: ("g", "sig1")}, edits[1]
    left, right = (mapping.child(base, rows) for rows in edits)
    if scenario == "wrong-parent":
        right = mapping.child(mapping.child(base, {}), edits[1])
    return left, right


def setup(repo, scenario):
    repo.mkdir()
    GIT(repo, "init", "--quiet", "--template=", "--object-format=sha1", "--initial-branch=research/all")
    declarations = {"contracts": declaration("contract", "public", {"value": 1})}
    ordinary = GIT(repo, "hash-object", "-w", "--stdin", payload="ordinary review bytes\n")
    source_tree = replace_blob(native.tree(repo, declarations), repo, ORDINARY_FILE, ordinary)
    source = native.object_commit(repo, source_tree, "semantic fixture")
    GIT(repo, "update-ref", HEAD, source)
    _, semantic = import_closed(read_inventory(repo, source))
    catalog = mapping.Catalog(semantic.root_hash, (
        (("api", "f"), "sig1"), (("api", "g"), "sig2"), (("cli", "g"), "cli-g"),
    ))
    if scenario == "catalog-mismatch":
        catalog = mapping.Catalog("other-semantic-root", catalog.signatures)
    base = mapping.Revision((), (), ((KEY, ("f", "sig1")),))
    left, right = inputs(scenario, base)
    GIT(repo, "update-ref", CURRENT, write_revision(repo, left))
    GIT(repo, "update-ref", INCOMING, write_revision(repo, right))
    GIT(repo, "update-ref", CATALOG, write_catalog(repo, catalog))
    return write_revision(repo, base), catalog, left, right


def exercise(root):
    results = {}
    for case in ("independent", "same-key", "same-key-divergent", "delete-update", "export-collision",
                 "wrong-signature", "wrong-parent",
                 "catalog-mismatch", "stale-current", "stale-incoming", "stale-catalog", "stale-head"):
        repo = root / case
        base, catalog, left, right = setup(repo, case)
        expected = capture(repo)
        changed = {}

        def race():
            if case == "stale-current":
                restored = mapping.child(mapping.child(left, {KEY: None}), {KEY: ("g", "sig2")})
                assert restored.entries == left.entries and restored.identity != left.identity
                changed[CURRENT] = write_revision(repo, restored)
            elif case == "stale-incoming":
                advanced = mapping.child(right, {("cli", "entry"): None})
                changed[INCOMING] = write_revision(repo, advanced)
            elif case == "stale-catalog":
                changed[CATALOG] = write_catalog(repo, mapping.Catalog("different-root", catalog.signatures))
            elif case == "stale-head":
                committed_tree = GIT(repo, "rev-parse", f"{expected.head}^{{tree}}")
                changed[HEAD] = native.object_commit(repo, committed_tree, "same tree again", (expected.head,))
            for name, address in changed.items():
                GIT(repo, "update-ref", name, address)

        result = join(repo, base, expected, race)
        if case == "independent":
            assert result["status"] == "published" and LOOKUP(repo, HEAD) == result["commit"]
            assert dict(result["entries"]) == {KEY: ("g", "sig2"), ("cli", "entry"): ("g", "cli-g")}
            assert read_revision(repo, LOOKUP(repo, CURRENT)).identity == result["mapping_revision"]
            assert result["semantic_root"] == catalog.semantic_root
            original_note = GIT(repo, "rev-parse", f"{expected.head}:{ORDINARY_FILE}")
            assert GIT(repo, "rev-parse", f'{result["commit"]}:{ORDINARY_FILE}') == original_note
            result["ordinary_blob_retained"] = original_note
            assert join(repo, base, expected)["status"] == "stale-before-prepare"
            checkout = root / "clean-clone"
            GIT(root, "clone", "--quiet", "--no-local", "--branch", "research/all", str(repo), str(checkout))
            _, rebuilt = import_closed(read_inventory(checkout, result["commit"]))
            assert rebuilt.root_hash == catalog.semantic_root
            exported = json.loads((checkout / MAPPING_FILE).read_text())
            assert exported["mapping"] == result["mapping_revision"] and exported["catalog"] == catalog.identity
            result["clean_clone"] = "same semantic and mapping identities"
        else:
            desired = ("catalog-snapshot-mismatch" if case == "catalog-mismatch" else
                       "ref-transaction-refused" if case.startswith("stale-") else "mapping-conflict")
            assert result["status"] == desired, (case, result)
            assert all(LOOKUP(repo, name) == changed.get(name, prior)
                       for name, prior in zip((HEAD, CURRENT, INCOMING, CATALOG),
                                              (expected.head, expected.ours, expected.theirs, expected.catalog)))
        results[case] = result
    return {"git": GIT(root, "--version"), "cases": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-mapping-coordination-") as directory:
        result = exercise(Path(directory))
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
