"""Check the Lean model and replay every archived operational comparison row."""

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BASELINE = "d554c0fdbdbb6814db6e5faf5dae3853f306b2d7"
CLAIM = "0012e8518096b149c93842580f905b1737d0a34a"
BATCH = 256


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def bool_term(value):
    assert type(value) is int and value in {0, 1}
    return "true" if value else "false"


def command_term(program):
    tag, *args = program
    if tag in {"skip", "fail", "read"}:
        return f".{tag}"
    if tag == "write":
        return f"(.write {bool_term(args[0])})"
    left, right = map(command_term, args)
    if tag in {"then", "else"}:
        return f"(.branch {'true' if tag == 'then' else 'false'} {left} {right})"
    assert tag in {"strict", "bind"}
    return f"(.{tag} {left} {right})"


def observation_term(observation):
    (tag, value), cell, history = observation
    if tag == "error":
        assert value == "planned"
        result = ".failed"
    elif value is None:
        result = ".unit"
    else:
        result = f".read {bool_term(value)}"
    events = ", ".join(f".{label} {bool_term(flag)}" for label, flag in history)
    return f"⟨{result}, {bool_term(cell)}, [{events}]⟩"


def pinned(path):
    raw = subprocess.check_output(["git", "show", f"{BASELINE}:{path.relative_to(ROOT)}"], cwd=ROOT)
    assert raw == path.read_bytes(), path
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", required=True, type=Path)
    args = parser.parse_args()
    lean = args.lean.resolve(strict=True)
    python = shutil.which("python3")
    env = os.environ | {"LC_ALL": "C", "PYTHONHASHSEED": "1"}
    runner = HERE / "run.py"
    evidence = pinned(HERE / "evidence.json")
    runner_bytes = pinned(runner)
    controls = []
    with tempfile.TemporaryDirectory(prefix="llmlang-state-result-proof-") as temporary:
        directory = Path(temporary)
        rows_file = directory / "operational.jsonl"
        observed = subprocess.check_output(
            [python, "-B", str(runner), "--rows", str(rows_file)], env=env, cwd=ROOT, timeout=30,
        )
        assert observed == evidence
        rows = rows_file.read_bytes()
        assert digest(rows) == json.loads(evidence)["comparison_rows_sha256"]
        model = HERE / "Observation.lean"
        proof = directory / model.name
        proof.write_bytes(model.read_bytes())
        version = subprocess.check_output([lean, "--version"], text=True).strip()
        assert "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9" in version
        env["LEAN_PATH"] = str(directory)
        axioms = subprocess.check_output(
            [lean, "-o", "Observation.olean", proof.name], cwd=directory, env=env, text=True, timeout=30,
        ).splitlines()
        assert len(axioms) == 4 and all(re.fullmatch(
            r"'ClosedStateResult\.[a-z_]+' depends on axioms: \[(propext)(, Quot.sound)?\]", line
        ) for line in axioms)
        statements = []
        for raw in rows.splitlines():
            program, initial, observation, _judgments = json.loads(raw)
            statements.append(f"example : denote {command_term(program)} {bool_term(initial)} = "
                              f"{observation_term(observation)} := by rfl")
        imports = "import Observation\nopen ClosedStateResult\n"
        batches = {}
        for start in range(0, len(statements), BATCH):
            batch = statements[start:start + BATCH]
            source = directory / f"Batch{start // BATCH}.lean"
            source.write_text(imports + "\n".join(batch) + "\n", encoding="utf-8")
            subprocess.run([lean, source.name], cwd=directory, env=env, check=True,
                           capture_output=True, timeout=30)
            batches[source.name] = {"checks": len(batch), "sha256": digest(source.read_bytes())}
        wrong = directory / "Wrong.lean"
        wrong.write_text(imports + "example : denote restoredCell false = denote .skip false := by rfl\n",
                         encoding="utf-8")
        failure = subprocess.run([lean, wrong.name], cwd=directory, env=env, text=True,
                                 capture_output=True, timeout=30)
        assert failure.returncode and "rfl" in failure.stdout and "definitionally equal" in failure.stdout
        controls.append({"name": "erased-restore-effects", "rejected": True, "source_sha256": digest(wrong.read_bytes())})
    print(json.dumps({
        "python": platform.python_version(), "lean": version, "operational_baseline": BASELINE,
        "proof_iteration_baseline": CLAIM, "model_sha256": digest(model.read_bytes()),
        "operational_sources": {"runner_sha256": digest(runner_bytes), "ledger_sha256": digest(evidence),
                                "comparison_rows_sha256": digest(rows)},
        "axioms": axioms, "checked_rows": len(statements),
        "batch_sizes": dict(sorted(Counter(item["checks"] for item in batches.values()).items())),
        "batches": batches, "controls": controls,
    }, indent=2))


if __name__ == "__main__":
    main()
