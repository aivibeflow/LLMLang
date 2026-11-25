"""Replay the exact Lean schedule model against each scoped Python observation."""

import argparse
from collections import Counter
from hashlib import sha256
import importlib.util
from itertools import product
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parents[1]
REPO = RESEARCH.parent
MODEL = RESEARCH / "language-design/RT-03/COMMON-RESOURCE-PROFILES-01"
BASE = "ccbb3e52"


def git(*args):
    return subprocess.check_output(["git", "-C", str(REPO), *args], text=True).strip()


def load():
    spec = importlib.util.spec_from_file_location("resource_profiles", MODEL / "check.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def audit(lean, work):
    pins = {}
    for name in ("check.py", "evidence.json"):
        path = MODEL / name
        relative = str(path.relative_to(REPO))
        blob = git("rev-parse", f"{BASE}:{relative}")
        assert blob == git("hash-object", relative)
        pins[relative] = blob
    model = load()
    leans = HERE / "Schedule.lean"
    expected_proofs = [
        f"'ResourceSchedule.{name}' does not depend on any axioms"
        for name in ("scalar_normal_form", "invariant_scalar_iff", "terminal_order_projection",
                     "terminal_order_injective")
    ]

    source_rows = []
    expected = []
    order_checks = 0
    invariant_checks = 0
    local_theory = Counter()
    order_forms = ("tpc", "tcp", "ptc", "pct", "ctp", "cpt")
    job_options = [model.Job(delta, retains) for delta, retains in product((-2, -1, 1, 2), (False, True))]
    for initial, a, b, target, grants in product((0, 1, 2), job_options, job_options, "ab", ("", "a", "b", "ab")):
        case = model.Input(initial, (a, b), target, frozenset(grants))
        peer = "b" if target == "a" else "a"
        target_job, peer_job = case.job(target), case.job(peer)
        source_rows.append(",".join(map(str, (
            initial, target_job.delta, peer_job.delta, int(target in grants), int(peer in grants)
        ))))
        rename = {"t": target, "p": peer, "c": "x"}
        orders = [tuple(rename[token] for token in order) for order in order_forms]
        observations = [model.actor(case, order) for order in orders]
        ordered_events = [tuple(event[1] if event[0] == "settle" else "x"
                                for event in record.trace if event[0] in ("settle", "cancel"))
                          for record in observations]
        if ordered_events != orders:
            raise ValueError("Full trace loses one of the required terminal-order events")
        scalars = [record.balance for record in observations]
        commute = scalars[0] == scalars[2]
        cancellation_invisible = scalars[0] == scalars[4]
        assert (len(set(scalars)) == 1) == (commute and cancellation_invisible)
        local_theory[f"commute_{int(commute)}_cancellation_invisible_{int(cancellation_invisible)}"] += 1
        expected.append(",".join(map(str, scalars)))
        order_checks += len(orders)
        invariant_checks += 1

    input_file = work / "cases.csv"
    input_file.write_text("\n".join(source_rows) + "\n")
    result = subprocess.run([lean, "--run", str(leans), str(input_file)], text=True, capture_output=True,
                            timeout=60, check=True).stdout.splitlines()
    assert result[:len(expected_proofs)] == expected_proofs
    assert result[len(expected_proofs):] == expected
    archive = json.loads((MODEL / "evidence.json").read_text())["counts"]
    assert local_theory["commute_1_cancellation_invisible_1"] == archive["actor_same_scalar_multi_trace"]
    return {
        "input_commit": git("rev-parse", BASE), "input_blobs": pins,
        "lean": subprocess.check_output([lean, "--version"], text=True).strip(),
        "lean_model_sha256": sha256(leans.read_bytes()).hexdigest(), "python": sys.version.split()[0],
        "axioms": expected_proofs, "finite_scalar_comparisons": order_checks,
        "finite_terminal_projection_comparisons": order_checks,
        "finite_invariance_checks": invariant_checks, "classification": local_theory,
        "matrix_inputs_sha256": sha256(input_file.read_bytes()).hexdigest(),
        "matrix_outputs_sha256": sha256(("\n".join(expected) + "\n").encode()).hexdigest(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", default="lean")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="resource-schedule-proof-") as directory:
        result = audit(args.lean, Path(directory))
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
