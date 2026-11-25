"""Compare projected and pointwise refinement with explicit input coverage."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import platform
import subprocess

HERE = Path(__file__).resolve().parent
ACTIVE = (0, 1)
THEOREMS = ("refinementsCompose", "lowerCoverageTransfers", "sameProjectedOutcomes",
            "projectionMissesWrongInput", "emptyRefinementWithoutCoverage")


def outcomes(mask):
    return {outcome for outcome in range(2) if mask & (1 << outcome)}


def check(spec, design, implementation, active=ACTIVE):
    spec_rows, design_rows, implementation_rows = (
        {x: outcomes(layer[x]) for x in active} for layer in (spec, design, implementation)
    )
    projected_spec = set().union(*spec_rows.values())
    projected_design = set().union(*design_rows.values())
    projected_implementation = set().union(*implementation_rows.values())
    projected = bool(projected_implementation) and projected_implementation <= projected_design <= projected_spec
    pointwise = all(implementation_rows[x] <= design_rows[x] <= spec_rows[x] for x in active)
    covered = all(implementation_rows.values())
    endpoint_only = all(implementation_rows[x] and implementation_rows[x] <= spec_rows[x] for x in active)
    return {
        "projected": projected, "pointwise": pointwise, "implementation_coverage": covered,
        "design_coverage": all(design_rows.values()), "layered_admission": pointwise and covered,
        "endpoint_only": endpoint_only,
    }


def independent_oracle(spec, design, implementation):
    for x in ACTIVE:
        implementations = [y for y in range(2) if implementation[x] & 1 << y]
        if not implementations:
            return False
        for y in range(2):
            bit = 1 << y
            if implementation[x] & bit and not design[x] & bit:
                return False
            if design[x] & bit and not spec[x] & bit:
                return False
    return True


def observe():
    counts = Counter()
    for spec in product(range(1, 4), repeat=2):
        for design in product(range(4), repeat=2):
            for implementation in product(range(4), repeat=2):
                result = check(spec, design, implementation)
                assert result["layered_admission"] == independent_oracle(spec, design, implementation)
                assert not result["layered_admission"] or result["design_coverage"]
                counts["cases"] += 1
                counts["projected"] += result["projected"]
                counts["pointwise_only"] += result["pointwise"]
                counts["pointwise_lacks_coverage"] += result["pointwise"] and not result["implementation_coverage"]
                counts["layered_admission"] += result["layered_admission"]
                counts["projected_misses_pointwise_violation"] += result["projected"] and not result["pointwise"]
                counts["projected_misses_coverage_gap"] += (
                    result["projected"] and result["pointwise"] and not result["implementation_coverage"]
                )
                counts["endpoint_only_ignores_layer_violation"] += (
                    result["endpoint_only"] and not result["layered_admission"]
                )
    assert counts["cases"] == 2304
    assert counts["layered_admission"] == 49 and counts["pointwise_only"] == 225
    controls = {
        "swapped_input_outcomes": check((1, 2), (1, 2), (2, 1)),
        "missing_implementation_input": check((1, 2), (1, 2), (1, 0)),
        "unsafe_design_outcome_unused_by_implementation": check((1, 2), (3, 2), (1, 2)),
        "submitted_scope_only": check((1, 2), (1, 2), (1, 0), (0,)),
        "pinned_required_scope": check((1, 2), (1, 2), (1, 0)),
    }
    assert controls["swapped_input_outcomes"]["projected"]
    assert not controls["swapped_input_outcomes"]["pointwise"]
    assert controls["missing_implementation_input"]["pointwise"]
    assert not controls["missing_implementation_input"]["layered_admission"]
    assert controls["unsafe_design_outcome_unused_by_implementation"]["endpoint_only"]
    assert not controls["unsafe_design_outcome_unused_by_implementation"]["layered_admission"]
    assert controls["submitted_scope_only"]["layered_admission"]
    assert not controls["pinned_required_scope"]["layered_admission"]
    return dict(counts), controls


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", type=Path, required=True)
    args = parser.parse_args()
    lean = args.lean.resolve()
    proof = HERE / "InputCoverage.lean"
    version = subprocess.check_output([lean, "--version"], text=True).strip()
    assert "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9" in version
    audit = subprocess.check_output([lean, "-DwarningAsError=true", proof], text=True).splitlines()
    assert audit == [f"'{name}' does not depend on any axioms" for name in THEOREMS]
    counts, controls = observe()
    files = (Path(__file__), proof)
    print(json.dumps({
        "schema": "llmlang-rt05-per-input-refinement/1", "python": platform.python_version(),
        "lean": version, "axiom_audit": audit,
        "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        "input_domain": ACTIVE, "outcome_domain": [0, 1], "counts": counts, "controls": controls,
    }, indent=2))


if __name__ == "__main__":
    main()
