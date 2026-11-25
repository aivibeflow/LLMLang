#!/usr/bin/env python3
"""Generate a bounded C witness and replay independently checked resource obligations."""

from copy import deepcopy
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
MODES = ("declared", "omitted-tail", "extra-tick", "wrong-provider")
PROVIDERS = {"base": (2, 5), "expensive": (2, 9)}
SHAPE = {"loop_start": 1, "loop_includes_n": True, "delta": -1,
         "enter": ["left", "right"], "provider_slots": ["tap_left", "tap_right"]}
DRIVER = """#include <stdio.h>
unsigned left_count, right_count, cost;
extern int tap_left(void);
extern int tap_right(void);
static int left(unsigned n);
static int right(unsigned n);

static int left(unsigned n) {
    if (n == 0) return 0;
    int selected = tap_left();
    EXTRA
    return selected + right(n - 1);
}

static int right(unsigned n) {
    if (n == 0) return 0;
    int selected = SELECT_RIGHT();
    return selected + left(n - 1);
}

int main(void) {
    unsigned n, side;
    while (scanf("%u %u", &n, &side) == 2) {
        if (n > 32 || side > 1) return 2;
        left_count = right_count = cost = 0;
        int sum = 0;
        for (unsigned i = 1; i OP n; ++i) {
            sum += side ? left(i) : right(i);
        }
        printf("%d %u %u %u\\n", sum, left_count, right_count, cost);
    }
    return ferror(stdin) || ferror(stdout);
}
"""
PROVIDER = """extern unsigned left_count, right_count, cost;
int tap_left(void) { left_count += 1; cost += LEFT_COST; return 1; }
int tap_right(void) { right_count += 1; cost += RIGHT_COST; return 1; }
"""


def fingerprint(payload):
    return sha256(payload).hexdigest()


def identity(payload):
    return fingerprint(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())


def run_tool(args, directory, payload=None):
    completed = subprocess.run(
        args, cwd=directory, input=payload, text=True, capture_output=True, check=True
    )
    assert not completed.stderr
    return completed.stdout


def generate(ir):
    if ir != SHAPE:
        raise ValueError("unsupported loop, decrease, or binding witness")
    return DRIVER.replace("OP", "<=").replace("EXTRA", "").replace("SELECT_RIGHT", "tap_right")


def source_for(mode):
    proven_shape = generate(SHAPE)
    if mode == "omitted-tail":
        return proven_shape.replace("i <= n", "i < n")
    if mode == "extra-tick":
        return proven_shape.replace("int selected = tap_left();", "int selected = tap_left(); (void)tap_left();")
    if mode == "wrong-provider":
        return proven_shape.replace("int selected = tap_right();", "int selected = tap_left();")
    assert mode == "declared"
    return proven_shape


def expected(n, side, weights):
    evaluations = [side ^ (step % 2) for i in range(1, n + 1) for step in range(i)]
    lcount = evaluations.count(1)
    rcount = len(evaluations) - lcount
    return len(evaluations), lcount, rcount, lcount * weights[0] + rcount * weights[1]


def build(directory, compiler, flags, mode, provider, weights):
    directory.mkdir()
    raw = source_for(mode)
    (directory / "driver.c").write_text(raw, encoding="utf-8")
    provider_source = PROVIDER.replace("LEFT_COST", str(weights[0])).replace("RIGHT_COST", str(weights[1]))
    (directory / "provider.c").write_text(provider_source, encoding="utf-8")
    for stem in ("driver", "provider"):
        run_tool([compiler, *flags, "-c", stem + ".c", "-o", stem + ".o"], directory)
    run_tool([compiler, "driver.o", "provider.o", "-o", "app"], directory)
    trials = list(product(range(33), (0, 1)))
    stdout = run_tool(["./app"], directory, "".join(f"{n} {side}\n" for n, side in trials))
    observations = {}
    for (n, side), line in zip(trials, stdout.splitlines(), strict=True):
        observations[n, side] = tuple(map(int, line.split()))
    differences = {
        metric: sum(row[index] != expected(n, side, weights)[index]
                    for (n, side), row in observations.items())
        for index, metric in enumerate(("return", "left", "right", "cost"))
    }
    assert all(value == 0 for value in differences.values()) == (mode == "declared")
    if mode in ("wrong-provider", "extra-tick"):
        assert differences["return"] == 0 and differences["cost"] > 0
    if mode == "omitted-tail":
        assert differences["return"] == 64
    baseline_failures = sum(cost > 5 * (n * (n + 1) // 2)
                            for (n, _), (_, _, _, cost) in observations.items())
    if mode == "declared":
        assert (baseline_failures != 0) == (provider == "expensive")
        assert all(cost <= max(weights) * (n * (n + 1) // 2)
                   for (n, _), (_, _, _, cost) in observations.items())
    return {
        "flags": flags, "mode": mode, "profile": provider, "weights": weights,
        "source": fingerprint(raw.encode()), "caller": fingerprint((directory / "driver.o").read_bytes()),
        "provider": fingerprint((directory / "provider.o").read_bytes()),
        "subject": fingerprint((directory / "app").read_bytes()),
        "observation": fingerprint(stdout.encode()), "count": len(trials),
        "differences": differences, "over_original_budget": baseline_failures,
    }


def graph(row, proof_digest):
    assert row["mode"] == "declared" and not any(row["differences"].values())
    translation = {
        "role": "finite-native-correspondence", "ir": identity(SHAPE),
        "generated_source": row["source"], "caller": row["caller"], "subject": row["subject"],
        "observations": row["observation"], "inputs": "n=0..32, phase=0 or 1",
    }
    recurrence = {
        "role": "symbolic-cost-recurrence", "ir": identity(SHAPE), "proof": proof_digest,
    }
    binding = {"role": "provider-cost", "artifact": row["provider"], "weights": row["weights"]}
    closed = {
        "role": "composed-pilot", "subject": row["subject"],
        "symbolic_cost_envelope": {"cap": max(row["weights"]), "size_factor": "triangular(n)"},
        "dependencies": [identity(item) for item in (translation, recurrence, binding)],
    }
    return translation, recurrence, binding, closed


def gate(expected_graph, supplied):
    nodes = {identity(node): node for node in supplied}
    expected_set = {identity(node) for node in expected_graph}
    if set(nodes) != expected_set:
        return "incomplete-or-stale"
    closed = nodes[identity(expected_graph[-1])]
    assert closed["role"] == "composed-pilot"
    assert set(closed["dependencies"]) == expected_set - {identity(closed)}
    return "exact-pilot"


def experiment(root):
    compiler = os.environ.get("CC", "gcc")
    lean = os.environ.get("LEAN", "lean")
    proof = (HERE / "Costs.lean").read_bytes()
    (root / "Costs.lean").write_bytes(proof)
    axioms = run_tool([lean, "-DwarningAsError=true", "Costs.lean"], root).splitlines()
    assert len(axioms) == 5 and all("sorryAx" not in line for line in axioms)
    assert all("does not depend on any axioms" in line or
               line.split("depends on axioms: ")[1] in {"[propext]", "[propext, Quot.sound]"} for line in axioms)
    malformed = deepcopy(SHAPE)
    malformed["delta"] = 0
    try:
        generate(malformed)
    except ValueError:
        pass
    else:
        raise AssertionError("nondecreasing recurrence admitted")

    rows = {}
    for level, mode, (provider, weights) in product(("-O0", "-O2"), MODES, PROVIDERS.items()):
        flags = ("-std=c11", "-Wall", "-Wextra", "-Werror", level)
        name = "/".join((level, mode, provider))
        rows[name] = build(root / name.replace("/", "-"), compiler, flags, mode, provider, weights)
    baseline = rows["-O2/declared/base"]
    expensive = rows["-O2/declared/expensive"]
    assert baseline["caller"] == expensive["caller"] and baseline["provider"] != expensive["provider"]
    proof_graph = graph(baseline, fingerprint(proof))
    changed_graph = graph(expensive, fingerprint(proof))
    assert gate(proof_graph, proof_graph) == "exact-pilot"
    assert gate(proof_graph, proof_graph[::-1]) == "exact-pilot"
    assert gate(changed_graph, proof_graph) == "incomplete-or-stale"
    assert gate(changed_graph, changed_graph) == "exact-pilot"
    controls = {}
    for i, node in enumerate(proof_graph):
        altered = proof_graph[:i] + proof_graph[i + 1:]
        decision = gate(proof_graph, altered)
        assert decision == "incomplete-or-stale"
        controls[node["role"]] = decision
    return {
        "format": "loop-call-correspondence-01",
        "gcc": run_tool([compiler, "--version"], root).splitlines()[0],
        "lean": run_tool([lean, "--version"], root).strip(), "axioms": axioms,
        "rows": rows, "observations": sum(row["count"] for row in rows.values()),
        "proof_graph": proof_graph, "omitted_node_controls": controls,
        "stale_binding": "incomplete-or-stale", "nondecreasing_recurrence": "refused",
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-loop-call-") as work:
        ledger = experiment(Path(work))
    text = json.dumps(ledger, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
