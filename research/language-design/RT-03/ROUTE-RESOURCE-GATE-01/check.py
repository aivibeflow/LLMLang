"""Compose source route extraction, work limits and exact feasibility evidence."""

import argparse
from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import subprocess
import sys


HERE = Path(__file__).resolve().parent
EXTRACTOR = HERE.parent / "SOURCE-DIFFERENCE-ROUTES-01" / "run.py"
CERTIFICATE = HERE.parent / "DIFFERENCE-CERTIFICATE-01" / "checker.py"
sys.path.insert(0, str(EXTRACTOR.parent))
from run import Certificate, classify, extract
from checker import checked_negative_walk


def source_for(family, vertices, negative):
    ring = [(index, index + 1, 1) for index in range(vertices - 1)]
    ring.append((vertices - 1, 0, -(vertices - 1) - negative))
    if family == "chords":
        ring.extend((a, b, b - a) for a in range(vertices - 2) for b in range(a + 2, vertices))
    elif family == "opposed":
        ring.extend((index + 1, index, -1) for index in range(vertices - 1))
    params = ", ".join(f"v{i}" for i in range(vertices))
    lines = [f"def route({params}):"]
    for index, (a, b, bound) in enumerate(ring):
        lines.append("    " * (index + 1) + f"if v{b} - v{a} <= {bound}:")
    lines.append("    " * (len(ring) + 1) + 'return "target"')
    lines.append('    return "fallback"')
    return "\n".join(lines) + "\n"


def target(source):
    selected = [route.query for route in extract(source) if route.value == "target"]
    assert len(selected) == 1
    return selected[0]


def solver(backend, executable, query, limit):
    flags = (["--lang=smt2", f"--rlimit={limit}"] if backend == "cvc5"
             else ["-in", "-smt2", f"rlimit={limit}"])
    try:
        result = subprocess.run([executable, *flags], input=query.formula(), text=True,
                                capture_output=True, check=True, timeout=5)
    except subprocess.TimeoutExpired:
        return "timeout"
    answer = result.stdout.strip()
    assert answer in {"sat", "unsat", "unknown"}, (answer, result.stderr)
    return answer


def run(cvc5, z3):
    versions = {name: {
        "banner": subprocess.check_output([exe, "--version"], text=True).splitlines()[0],
        "sha256": sha256(Path(exe).read_bytes()).hexdigest(),
    } for name, exe in (("cvc5", cvc5), ("z3", z3))}
    totals = Counter()
    cases = []
    for family, vertices, negative in product(("ring", "chords", "opposed"), (3, 5, 8), (0, 1)):
        source = source_for(family, vertices, negative)
        query = target(source)
        alternate = target("# formatting-only revision\n" + source)
        assert query.identity != alternate.identity and query.formula() == alternate.formula()
        control = Certificate(query.identity, tuple(range(vertices)))
        assert checked_negative_walk(query, control) == bool(negative)
        assert not checked_negative_walk(alternate, control)
        potential = tuple(range(vertices))
        witness = all(potential[edge.destination] - potential[edge.source] <= edge.bound
                      for edge in query.constraints)
        assert witness == (not negative)
        results = []
        for (backend, exe), limit in product((("cvc5", cvc5), ("z3", z3)), (1, 100, 100_000)):
            status = solver(backend, exe, query, limit)
            assert status in {"unknown", "timeout", "unsat" if negative else "sat"}
            if limit == 100_000:
                assert status in {"sat", "unsat"}, (backend, family, vertices, status)
            adjusted = status if status in {"sat", "unsat"} else "unknown"
            assert classify(query, adjusted)[1]
            assert classify(alternate, adjusted, control)[1]
            pruned = not classify(query, adjusted, control)[1]
            assert pruned == (status == "unsat" and bool(negative))
            verified_witness = status == "sat" and witness
            outcome = "pruned" if pruned else "possible-verified" if verified_witness else "possible-unresolved"
            totals[outcome] += 1
            results.append({"backend": backend, "limit": limit, "status": status, "outcome": outcome})
        cases.append({
            "family": family, "vertices": vertices, "negative": bool(negative), "constraints": len(query.constraints),
            "source_sha256": sha256(source.encode()).hexdigest(), "route": query.identity,
            "format_variant_route": alternate.identity, "formula_sha256": sha256(query.formula().encode()).hexdigest(),
            "checked_potential": potential if witness else None, "walk_indices": control.edges if negative else None,
            "controls": results,
        })
    return {
        "python": platform.python_version(), "solvers": versions, "cases": cases,
        "source_sha256": {path.name: sha256(path.read_bytes()).hexdigest()
                          for path in (Path(__file__).resolve().with_name("check.py"), EXTRACTOR, CERTIFICATE)},
        "totals": dict(totals),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cvc5", required=True)
    parser.add_argument("--z3", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.cvc5, args.z3), indent=2, sort_keys=True))
