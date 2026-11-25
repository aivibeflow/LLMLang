#!/usr/bin/env python3
"""Bind source call inventory, observed SPG traces, and guarded may dependencies."""

import ast
from collections import Counter
from hashlib import sha256
from io import BytesIO
from itertools import product
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from tarfile import open as open_tar
import tempfile

HERE = Path(__file__).resolve().parent
ARCHIVE = "22d607ba6f24ff187877a2da500892a3fc2b043b"
PROTOTYPE = "research/PROTOTYPES/DEPENDENCY-GRAPH-01"
INTS = (-2, -1, 0, 1, 2)
PROVIDERS = ("alpha", "beta", "gamma")
ENABLED_GATES = {"true": (True,), "false": (False,), "unknown": (False, True)}


def read_calls(term, path=(), guards=()):
    match term:
        case ["if", test, yes, no]:
            yield from read_calls(yes, (*path, 2), (*guards, (test, True)))
            yield from read_calls(no, (*path, 3), (*guards, (test, False)))
        case [("op" | "pin") as mode, index, ["argument", 0]]:
            yield mode, index, path, guards
        case _:
            raise ValueError(f"Unsupported call or control form: {term!r}")


def test_guard(expr, n, gate):
    match expr:
        case ["argument", 1]:
            return gate
        case ["eq", ["argument", 0], ["literal", point]] if type(point) is int:
            return n == point
        case _:
            raise ValueError(f"Unsupported condition: {expr!r}")


def select_source(first, second):
    return (f'(op("alpha", n) if n == {first} else op("beta", n)) if gate else '
            f'(pin("gamma", n) if n == {second} else op("beta", n))')


def source_census(source):
    return Counter((node.func.id, node.args[0].value)
                   for node in ast.walk(ast.parse(source, mode="eval"))
                   if isinstance(node, ast.Call))


def build(first, second, compile_program, observe, Program, Operation, Implementation):
    body = select_source(first, second)
    names = (*PROVIDERS, "entry")
    semantics = {name: ((name,),) for name in PROVIDERS}
    semantics["entry"] = tuple((name,) for name in PROVIDERS)
    declarations = {name: Operation(name, ("Int",) if name != "entry" else ("Int", "Bool"),
                                    "Int", name) for name in names}
    functions = {name: Implementation(name, ("n",), f'emit("{name}", n+{i})')
                 for i, name in enumerate(PROVIDERS)}
    functions["entry"] = Implementation("entry", ("n", "gate"), body)
    program = Program(semantics, declarations, functions, {name: name for name in PROVIDERS})
    compiled = compile_program(program)
    root = compiled.snapshot.mapping["implementation:entry"]
    _, _, encoded, *refs = compiled.store.get(root).payload
    aliases = {}
    owners = {}
    for name in PROVIDERS:
        address = compiled.snapshot.mapping[f"implementation:{name}"]
        owners[name] = address
        operation = compiled.store.get(address).payload[1]["external"]
        aliases[("op", operation)] = name
        aliases[("pin", address)] = name
    bindings = {}
    for slot, address in compiled.snapshot.selections:
        if slot.startswith("binding:"):
            refs_by_role = {edge.relation: edge.target_hash
                            for edge in compiled.store.get(address).dependencies}
            bindings[refs_by_role["operation"]] = (address, refs_by_role["implementation"])
    ready = []
    indexes = set()
    for mode, reference, path, guards in read_calls(json.loads(encoded["literal"])):
        if type(reference) is not int or reference in indexes or not 0 <= reference < len(refs):
            raise AssertionError((root, reference))
        indexes.add(reference)
        edge = refs[reference]["external" if mode == "op" else "exact_call"]
        provider = aliases[mode, edge]
        binding, selected = bindings[edge] if mode == "op" else (None, edge)
        if selected != owners[provider]:
            raise AssertionError(("Unexpected selected provider", mode, provider, selected))
        ready.append({"mode": mode, "path": path, "guards": guards, "provider": provider,
                      "reference": edge, "binding": binding, "resolved_implementation": selected})
    assert indexes == set(range(len(refs)))
    assert source_census(body) == Counter((site["mode"], site["provider"]) for site in ready)
    points = {}
    for n, gate in product(INTS, (False, True)):
        numeric, trace = observe(compiled, "entry", (n, gate))
        expected = ("alpha" if n == first else "beta") if gate else (
            "gamma" if n == second else "beta")
        feasible = [site["provider"] for site in ready
                    if all(test_guard(guard, n, gate) == polarity for guard, polarity in site["guards"])]
        if feasible != [expected] or trace != (expected,) or numeric != n + PROVIDERS.index(expected):
            raise AssertionError((first, second, n, gate, feasible, trace, expected))
        points[n, gate] = expected
    return root, compiled.snapshot.root_hash, ready, points


def compare_cases(api):
    counts, d = Counter(), sha256()
    witness = {}
    records, examples = [], []
    for first, second in product(INTS, repeat=2):
        root, snapshot, sites, points = build(first, second, api.compile_program, api.observe,
                                             api.Program, api.Operation, api.Implementation)
        records.append({"first": first, "second": second, "root": root, "snapshot": snapshot,
                        "sites": sites})
        examples.extend(f"example : selected ({first}) ({second}) ({n}) {str(gate).lower()} = "
                        f".{winner} := by decide" for (n, gate), winner in points.items())
        counts["compiled_source_profiles"] += 1
        counts["typed_site_occurrences"] += len(sites)
        counts["runtime_rows"] += len(points)
        for mask, (profile, gates) in product(range(1, 1 << len(INTS)), ENABLED_GATES.items()):
            domain = tuple(n for i, n in enumerate(INTS) if mask & (1 << i))
            expected = {points[n, gate] for n, gate in product(domain, gates)}
            exact = {site["provider"] for site in sites if any(
                all(test_guard(test, n, gate) == polarity for test, polarity in site["guards"])
                for n, gate in product(domain, gates))}
            if exact != expected:
                raise AssertionError((profile, domain, root, expected, exact))
            possible_without_guards = {site["provider"] for site in sites}
            if not expected <= possible_without_guards:
                raise AssertionError("The static may bound omitted a reachable provider")
            first_sample = {points[domain[0], gates[0]]}
            guessed_gate = {points[n, False] for n in domain} if profile == "unknown" else expected
            counts["may_dependency_requests"] += 1
            counts["static_has_extras"] += possible_without_guards != expected
            counts["sample_only_misses"] += bool(expected - first_sample)
            counts["assume_unknown_false_misses"] += bool(expected - guessed_gate)
            if expected - guessed_gate:
                witness.setdefault("unknown_false", {"first": first, "second": second,
                                                       "domain": domain, "required": sorted(expected),
                                                       "guessed": sorted(guessed_gate)})
            if expected - first_sample:
                witness.setdefault("sample_only", {"first": first, "second": second,
                                                    "domain": domain, "gates": gates,
                                                    "required": sorted(expected),
                                                    "observed": sorted(first_sample)})
            d.update(json.dumps([first, second, mask, profile, sorted(expected)]).encode() + b"\n")
    return counts, witness, records, examples, d.hexdigest()


def kernel(directory, examples):
    lean = os.environ.get("LEAN", "lean")
    (directory / "Guard.lean").write_bytes((HERE / "Guard.lean").read_bytes())
    core = subprocess.check_output([lean, "-DwarningAsError=true", "-o", "Guard.olean", "Guard.lean"],
                                   cwd=directory, text=True)
    if core != (HERE / "axioms.txt").read_text():
        raise AssertionError(core)
    text = "import Guard\n" + "\n".join(examples) + "\n"
    (directory / "Cases.lean").write_text(text)
    subprocess.run([lean, "-DwarningAsError=true", "Cases.lean"], cwd=directory,
                   env={**os.environ, "LEAN_PATH": str(directory)}, check=True)
    return sha256(text.encode()).hexdigest()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as work:
        directory = Path(work)
        archive = subprocess.check_output(["git", "archive", ARCHIVE, PROTOTYPE])
        with open_tar(fileobj=BytesIO(archive), mode="r:") as source:
            source.extractall(directory, filter="data")
        sys.path.insert(0, str(directory / PROTOTYPE))
        from src import spg_representation as api
        counts, witnesses, records, examples, digest = compare_cases(api)
        verified = kernel(directory, examples)
    print(json.dumps({
        "schema": "llmlang-spg-guarded-dependency-discovery/1", "python": platform.python_version(),
        "archive_revision": ARCHIVE, "lean_observations_sha256": verified,
        "sources_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ("run.py", "Guard.lean", "axioms.txt")},
        "counts": counts, "witnesses": witnesses,
        "exact_spg_corpus_sha256": sha256(json.dumps(records, sort_keys=True).encode()).hexdigest(),
        "dependency_request_rows_sha256": digest,
    }, indent=2))
