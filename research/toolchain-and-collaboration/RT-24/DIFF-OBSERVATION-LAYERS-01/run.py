"""Compare byte, surface, typed graph and observation changes on pinned trees."""

import ast
import hashlib
import json
import platform
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "COMMIT-TREE-SEMANTIC-ROOT-01"))
from run import git, make_commit, make_tree
from src.spg_admission import validate
from src.spg_representation import (
    Implementation, Operation, Prefix, Program, RepresentationError, compile_program, observe,
)

BASELINE = "321d7a0c00db0e9fbaa2b3ea24c436b882c76cb0"
INPUTS = (-2, -1, 0, 1, 2)
INFIX = 'op("compute", x)'


def inspect(repo, tree):
    names = set(git(repo, "ls-tree", "--name-only", tree).decode().splitlines())
    if not {"program.json"} <= names <= {"program.json", "README.md"}:
        raise ValueError("tree is outside the fixture inventory")
    declaration = json.loads(git(repo, "show", f"{tree}:program.json"))
    if set(declaration) != {"surface", "entry", "binding"}:
        raise ValueError("unexpected declaration fields")
    surface, term = declaration["surface"], declaration["entry"]
    if surface == "infix":
        shape = ast.dump(ast.parse(term, mode="eval"), include_attributes=False)
        body = term
    elif surface == "prefix":
        shape = json.loads(term)
        body = Prefix(term)
    else:
        raise ValueError("unknown expression surface")
    graph = compile_program(Program(
        contracts={"quiet": ((),)},
        operations={
            "compute": Operation("Compute", ("Int",), "Int", "quiet"),
            "entry": Operation("Entry", ("Int",), "Int", "quiet"),
        },
        implementations={
            "plus": Implementation("compute", ("x",), "x + 1"),
            "minus": Implementation("compute", ("x",), "x - 1"),
            "entry": Implementation("entry", ("x",), body),
        },
        bindings={"compute": declaration["binding"]},
    ))
    validate(graph)
    slots = dict(graph.snapshot.selections)
    selected_binding = graph.store.get(slots["binding:compute"])
    selected_provider = next(edge.target_hash for edge in selected_binding.dependencies
                             if edge.relation == "implementation")
    return {
        "surface": {"grammar": surface, "body": shape},
        "semantic_root": graph.snapshot.root_hash, "slots": slots,
        "compute_provider": selected_provider,
        "observations": [observe(graph, "entry", (i,)) for i in INPUTS],
    }


def input_rows():
    source = {"surface": "infix", "entry": INFIX, "binding": "plus"}

    def files(declaration, *, expand=False, docs=b"Baseline notes.\n"):
        options = {"indent": 2, "sort_keys": True} if expand else {}
        return {"program.json": (json.dumps(declaration, **options) + "\n").encode(),
                "README.md": docs}

    yield "baseline", files(source), []
    yield "identical", files(source), [False, False, False, False]
    yield "docs-only", files(source, docs=b"Updated notes.\n"), [True, False, False, False]
    yield "source-format", files(source | {"entry": "(" + INFIX + ")"}, expand=True), [
        True, False, False, False,
    ]
    prefix = {"surface": "prefix", "entry": '["op","compute",["arg","x"]]'}
    yield "different-surface", files(source | prefix), [True, True, False, False]
    yield "retarget-provider", files(source | {"binding": "minus"}), [True, False, True, True]
    yield "explicit-neutral-add", files(source | {"entry": INFIX + " + 0"}), [True, True, True, False]
    yield "value-changing-body", files(source | {"entry": INFIX + " + 1"}), [True, True, True, True]
    yield "invalid-provider", files(source | {"binding": "absent"}), None


def run(repo):
    git(repo, "init", "--quiet", "--initial-branch=research/all", "--object-format=sha1")
    rows = iter(input_rows())
    _, sources, _ = next(rows)
    old_tree = make_tree(repo, sources)
    base = make_commit(repo, old_tree, "baseline")
    before = inspect(repo, old_tree)
    findings = {}
    for name, sources, expected in rows:
        tree = make_tree(repo, sources)
        revision = make_commit(repo, tree, name, base)
        patch = git(repo, "diff", "--no-color", "--no-ext-diff", "--no-textconv",
                    "--no-renames", base, revision).decode()
        try:
            after = inspect(repo, tree)
        except RepresentationError as error:
            assert expected is None and str(error) == "unknown implementation: absent"
            findings[name] = {"candidate": revision, "raw_patch": patch, "admission_error": str(error)}
            continue
        changed = [
            bool(patch),
            before["surface"] != after["surface"],
            before["semantic_root"] != after["semantic_root"],
            before["observations"] != after["observations"],
        ]
        assert changed == expected, (name, changed, expected)
        changed_slots = {
            slot: {"before": address, "after": after["slots"][slot]}
            for slot, address in sorted(before["slots"].items()) if address != after["slots"][slot]
        }
        assert bool(changed_slots) == changed[2]
        if name == "retarget-provider":
            assert list(changed_slots) == ["binding:compute"]
            assert after["compute_provider"] == before["slots"]["implementation:minus"]
        elif name in {"explicit-neutral-add", "value-changing-body"}:
            assert list(changed_slots) == ["implementation:entry"]
        findings[name] = {"candidate": revision, "tree": tree, "raw_patch": patch,
                          "changed": changed, "changed_slots": changed_slots, "snapshot": after}
    return {"base_commit": base, "base_tree": old_tree, "base_snapshot": before, "cases": findings}


def main():
    with tempfile.TemporaryDirectory(prefix="rt24-diff-layers-") as temp:
        evidence = run(Path(temp))
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
        "python": platform.python_version(), "inputs": INPUTS,
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_sha256": pins, **evidence,
    }, indent=2))


if __name__ == "__main__":
    main()
