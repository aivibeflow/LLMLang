#!/usr/bin/env python3
"""Compare budget proof reuse across exact provider, cost profile and contract changes."""

import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
SIZES = (*range(65), 127, 128, 256)
PROVIDERS = {
    "first": ((1, 1), (1, 0)),
    "equivalent": ((2, 1), (0, 0)),
    "slower": ((2, 1), (1, 0)),
    "smaller": ((1, 0), (0, 0)),
}
WEIGHTS = {"unit": (1, 1), "heavy": (1, 3)}
BUDGETS = {"base": (2, 1), "tight": (1, 0)}
# Providers have the same returned value and public function name.
# Distinct snapshots explicitly supply or omit a certificate for the current tuple.
CASES = {
    "base": ("first", "unit", "base", "current"),
    "equal_cost_rebind": ("equivalent", "unit", "base", "current"),
    "lower_cost_rebind": ("smaller", "unit", "base", "current"),
    "higher_cost_rebind": ("slower", "unit", "base", "current"),
    "more_expensive_profile": ("first", "heavy", "base", "current"),
    "tighter_budget": ("first", "unit", "tight", "current"),
    "lower_cost_tighter_budget": ("smaller", "unit", "tight", "current"),
    "missing_proof": ("equivalent", "unit", "base", None),
    "old_provider_proof": ("equivalent", "unit", "base", "base"),
    "old_proof_for_slower_provider": ("slower", "unit", "base", "base"),
    "old_profile_proof": ("first", "heavy", "base", "base"),
}
LEAN_COMMIT = "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9"


def digest(raw):
    if isinstance(raw, str):
        raw = raw.encode()
    return sha256(raw).hexdigest()


def affine(vector, size):
    return vector[0] * size + vector[1]


def summary(provider, profile):
    reads, callbacks = PROVIDERS[provider]
    read, callback = WEIGHTS[profile]
    return tuple(read * a + callback * b for a, b in zip(reads, callbacks, strict=True))


def identity(provider, profile, budget):
    payload = {
        "provider": {"name": provider, "events": PROVIDERS[provider], "value": "n+7"},
        "profile": {"scope": "provider_event_count", "weights": WEIGHTS[profile]},
        "budget": BUDGETS[budget], "size_domain": "Nat",
    }
    return digest(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def native_source():
    calls = []
    for provider, (reads, callbacks) in PROVIDERS.items():
        calls.append(f"""\
    for (size_t index = 0; index < sizeof(sizes) / sizeof(sizes[0]); ++index) {{
        uint64_t n = sizes[index];
        uint64_t read_count = 0;
        uint64_t callback_count = 0;
        for (uint64_t event = 0; event < {reads[0]} * n + {reads[1]}; ++event) {{
            ++read_count;
        }}
        for (uint64_t event = 0; event < {callbacks[0]} * n + {callbacks[1]}; ++event) {{
            ++callback_count;
        }}
        printf("{provider} %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 "\\n",
               n, n+7, read_count, callback_count);
    }}
""")
    return (
        "#include <inttypes.h>\n#include <stdint.h>\n#include <stdio.h>\n"
        "int main(void)\n{\n"
        + "    const uint64_t sizes[] = {" + ", ".join(map(str, SIZES)) + "};\n"
        + "".join(calls) + "    return 0;\n}\n"
    )


def execute(args, cwd=None, env=None, check=True):
    process = subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True,
                             timeout=60, check=False)
    if check and (process.returncode or process.stderr):
        raise RuntimeError(process.stdout + process.stderr)
    return process


def facts():
    combinations = dict.fromkeys(case[:3] for case in CASES.values())
    declarations = ["import CallCost", "open CallCost"]
    results = {}
    names = []
    for number, (provider, profile, budget) in enumerate(combinations):
        handle = f"case{number}"
        name = [f"{handle}{part}" for part in ("Provider", "Weights", "Budget")]
        body = PROVIDERS[provider]
        profile_weights = WEIGHTS[profile]
        limit = BUDGETS[budget]
        declarations.extend([
            f"def {name[0]} : Provider := ⟨⟨{body[0][0]}, {body[0][1]}⟩, ⟨{body[1][0]}, {body[1][1]}⟩⟩",
            f"def {name[1]} : Weights := ⟨{profile_weights[0]}, {profile_weights[1]}⟩",
            f"def {name[2]} : Affine := ⟨{limit[0]}, {limit[1]}⟩",
        ])
        rate, fixed = summary(provider, profile)
        if rate <= limit[0] and fixed <= limit[1]:
            witness = None
            declarations.extend([
                f"theorem {handle}Fits : fits (summarize {name[0]} {name[1]}) {name[2]} := by decide",
                f"theorem {handle}Proof (n : Nat) : concrete {name[0]} {name[1]} n ≤ evaluate {name[2]} n :=\n"
                f"  scoped_call {handle}Fits n",
            ])
        else:
            witness = 0 if fixed > limit[1] else 1 + limit[1]
            declarations.append(
                f"theorem {handle}Proof : evaluate {name[2]} {witness} < "
                f"concrete {name[0]} {name[1]} {witness} := by decide"
            )
        fact_name = f"{handle}Proof"
        names.append(fact_name)
        results[(provider, profile, budget)] = {
            "provider": provider, "profile": profile, "budget": budget,
            "exact_key": identity(provider, profile, budget), "summary": (rate, fixed), "theorem": fact_name,
            "status": "proven" if witness is None else "refuted", "witness": witness,
        }

    core = "\n\n".join(declarations) + "\n"
    audited = core + "\n".join(f"#print axioms {name}" for name in names) + "\n"
    wrong_application = (
        "theorem staleCostBudget (n : Nat) :\n"
        "  concrete case3Provider case3Weights n ≤ evaluate case3Budget n :=\n"
        "  scoped_call case0Fits n\n"
    )
    return audited, core + wrong_application, results


def axioms(output):
    pattern = re.compile(r"^'([^']+)' (?:does not depend on any axioms|depends on axioms: \[(.*)\])$")
    data = {}
    for line in output.splitlines():
        value = pattern.fullmatch(line)
        if value is None:
            raise ValueError(f"Unexpected Lean output {line!r}")
        theorem, dependencies = value.groups()
        data[theorem] = dependencies.split(", ") if dependencies else []
    if any(set(values) - {"propext", "Quot.sound"} for values in data.values()):
        raise ValueError("Unexpected axiom dependence")
    return data


def models(compiler, lean, source, claims, bad):
    with TemporaryDirectory(prefix="llmlang-call-cost-") as temporary:
        root = Path(temporary)
        (root / "Providers.c").write_text(source, encoding="utf-8")
        shutil.copy(HERE / "CallCost.lean", root / "CallCost.lean")
        (root / "BudgetClaims.lean").write_text(claims, encoding="utf-8")
        (root / "Stale.lean").write_text(bad, encoding="utf-8")
        env = {**os.environ, "LEAN_PATH": str(root)}
        flags = [lean, "-DwarningAsError=true"]
        audited_model = axioms(execute([*flags, "-o", "CallCost.olean", "CallCost.lean"], root, env).stdout)
        checked_claims = axioms(execute([*flags, "BudgetClaims.lean"], root, env).stdout)
        failure = execute([*flags, "Stale.lean"], root, env, check=False)
        diagnostics = failure.stdout + failure.stderr
        if not failure.returncode or "type mismatch" not in diagnostics.lower():
            raise ValueError(f"Expected stale proof rejection: {diagnostics}")
        native = []
        for opt in ("0", "3"):
            execute([compiler, "-std=c17", "-Wall", "-Wextra", "-Werror", f"-O{opt}",
                     "Providers.c", "-o", "providers"], root)
            native.append(execute(["./providers"], root).stdout)
        assert native[0] == native[1]
    return native[0], audited_model, checked_claims


def expected_native(output):
    observations = {}
    for line in output.splitlines():
        name, size, answer, reads, callbacks = line.split()
        n, value, measured_reads, measured_callbacks = map(int, (size, answer, reads, callbacks))
        model_reads, model_callbacks = PROVIDERS[name]
        assert (value, measured_reads, measured_callbacks) == (
            n + 7, affine(model_reads, n), affine(model_callbacks, n),
        )
        observations[(name, n)] = (measured_reads, measured_callbacks)
    assert len(observations) == len(PROVIDERS) * len(SIZES)
    return observations


def policies(certificates, native):
    base = certificates[CASES["base"][:3]]
    results = []
    counts = {policy: Counter(proven=0, refuted=0, unknown=0, false_proofs=0, unbound_proofs=0)
              for policy in ("functional_contract", "same_exact_key", "checked_rebind")}
    for name, (provider, weight, budget, offer) in CASES.items():
        current = certificates[(provider, weight, budget)]
        delivered = current if offer == "current" else base if offer == "base" else None
        fits = current["status"] == "proven"
        same = delivered is not None and current["exact_key"] == delivered["exact_key"]
        if not fits:
            n = current["witness"]
            reads, callbacks = native[(provider, n)]
            a, b = WEIGHTS[weight]
            assert a * reads + b * callbacks > affine(BUDGETS[budget], n)
        decisions = {
            "functional_contract": "proven",
            "same_exact_key": "proven" if current["exact_key"] == base["exact_key"] else "unknown",
            "checked_rebind": delivered["status"] if same else "unknown",
        }
        for policy, decision in decisions.items():
            counts[policy][decision] += 1
            counts[policy]["false_proofs"] += decision == "proven" and not fits
            counts[policy]["unbound_proofs"] += decision == "proven" and not same
        results.append({"case": name, "current": current["exact_key"],
                        "offered": delivered["exact_key"] if delivered else None,
                        "actual_budget_status": current["status"], "decisions": decisions})
    return counts, results


def replay(args):
    version = execute([args.lean, "--version"]).stdout.strip()
    assert LEAN_COMMIT in version
    c_source = native_source()
    lean_source, bad_proof, certificates = facts()
    native, model, audit = models(args.cc, args.lean, c_source, lean_source, bad_proof)
    assert set(audit) == {certificate["theorem"] for certificate in certificates.values()}
    observed = expected_native(native)
    stats, runs = policies(certificates, observed)
    return {
        "schema": "llmlang-call-cost-binding/1", "lean": version, "python": platform.python_version(),
        "compiler": execute([args.cc, "--version"]).stdout.splitlines()[0],
        "source_sha256": {name: digest((HERE / name).read_bytes()) for name in ("CallCost.lean", "run.py")},
        "generated_c_sha256": digest(c_source), "generated_lean_sha256": digest(lean_source),
        "native_abstract_observations": 2 * len(observed), "native_stdout_sha256": digest(native),
        "model_axioms": model, "claim_axioms": audit, "stale_direct_proof_application": "refused",
        "certificates": list(certificates.values()), "policies": stats, "snapshots": runs,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--lean", default="lean")
    print(json.dumps(replay(parser.parse_args()), indent=2))
