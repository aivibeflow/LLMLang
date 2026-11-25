"""Check Rust phase and ownership diagnostics plus exact native transition outcomes."""

import argparse
from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
MAXIMUM = 2**64 - 1
SETUP = "use typestate::{Ledger, Units};\nfn main() {\n    let mut ledger = Ledger::new(3, 0, 0);\n"
PREPARE = "let permit = ledger.draft().prepare(Units::new(2).unwrap());"
CONTROL_BODIES = {
    "typed-flow": (PREPARE + "\nlet _ = permit.submit(&mut ledger);", None),
    "submit-draft": ("let _ = ledger.draft().submit(&mut ledger);", "E0599"),
    "clone-prepared": (PREPARE + "\nlet _ = permit.clone();", "E0599"),
    "reuse-consumed": (PREPARE + "\nlet _ = permit.submit(&mut ledger);\n"
                       "let _ = permit.submit(&mut ledger);", "E0382"),
    "construct-unchecked-units": ("let _ = Units(6);", "E0423"),
}


def execute(arguments, directory, check=True):
    return subprocess.run(arguments, cwd=directory, check=check, capture_output=True,
                          text=True, timeout=60)


def oracle():
    rows = []
    summary = Counter()
    for same_owner, generation, total, revise, units in product(
        (True, False), (0, 7, MAXIMUM - 1, MAXIMUM), (0, 7, MAXIMUM - 2, MAXIMUM),
        (False, True), range(8),
    ):
        advanced = revise and generation < MAXIMUM
        live = generation + int(advanced)
        if units not in (1, 2, 3):
            verdict = "invalid-units"
        elif not same_owner:
            verdict = "wrong-owner"
        elif advanced:
            verdict = "stale"
        elif live == MAXIMUM or total + units > MAXIMUM:
            verdict = "exhausted"
        else:
            verdict = "committed"
            live += 1
            total += units
        summary[verdict] += 1
        rows.append(f"{str(advanced).lower()} {verdict} {live} {total}")
    rows.append("same-generation 1 1")
    return rows, dict(sorted(summary.items()))


def try_compile(rustc, work, library):
    results = {}
    for name, (body, expected_error) in CONTROL_BODIES.items():
        path = work / "control.rs"
        path.write_text(SETUP + body + "\n}\n", encoding="utf-8")
        executed = execute([rustc, "--edition=2021", "--emit=metadata",
                            "--extern", f"typestate={library}", str(path)], work, check=False)
        errors = re.findall(r"^error\[(E\d+)\]", executed.stderr, re.MULTILINE)
        if (executed.returncode == 0, errors) != (expected_error is None,
                                                  [] if expected_error is None else [expected_error]):
            raise AssertionError((name, expected_error, executed.stderr))
        results[name] = expected_error or "admitted"
    return results


def verify(rustc, work):
    fingerprint = execute([rustc, "-vV"], work).stdout.splitlines()
    if "release: 1.85.1" not in fingerprint:
        raise ValueError(fingerprint)
    rows, summary = oracle()
    builds = {}
    control_results = None
    for level in (0, 3):
        archive = work / "libtypestate.rlib"
        execute([rustc, "--edition=2021", "--crate-type=rlib", "-D", "warnings",
                 f"-Copt-level={level}", str(HERE / "typestate.rs"), "-o", str(archive)], work)
        checked = try_compile(rustc, work, archive)
        if control_results is None:
            control_results = checked
        elif checked != control_results:
            raise ValueError("Frontend admission changed across library profiles")
        binary = work / f"probe-O{level}"
        execute([rustc, "--edition=2021", "-D", "warnings", f"-Copt-level={level}",
                 "--extern", f"typestate={archive}", str(HERE / "probe.rs"), "-o", str(binary)], work)
        observed = execute([str(binary)], work).stdout
        if observed.splitlines() != rows:
            raise AssertionError((level, "native ledger disagreed with the transition oracle"))
        builds[f"O{level}"] = {"matrix_rows": len(rows) - 1,
                              "same_generation_consumption_checked": True,
                              "trace_sha256": sha256(observed.encode()).hexdigest()}

    return {
        "rustc": fingerprint,
        "sources": {name: sha256((HERE / name).read_bytes()).hexdigest()
                    for name in ("typestate.rs", "probe.rs", "run.py")},
        "compiler_controls": control_results,
        "results_per_profile": summary,
        "builds": builds,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rustc", default="rustc")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-native-typestate-") as work:
        print(json.dumps(verify(args.rustc, Path(work)), indent=2))
