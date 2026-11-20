"""Fail-closed process adapter for cvc5 CPC proofs and Logos.

This adapter deliberately never issues a language-level PROVEN status. Logos's
CLI verdict is still unbound to the expected LLMLang query until the Lean
assumption-binding wrapper from Scenario 29 is implemented.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Literal


RunStatus = Literal[
    "SOLVER_REPORTED_SAT",
    "SOLVER_REPORTED_UNSAT",
    "SOLVER_REPORTED_UNKNOWN",
    "CHECKER_REPORTED_CORRECT_UNBOUND",
    "CHECKER_REPORTED_INCORRECT",
    "CHECKER_REPORTED_INCOMPLETE",
    "UNKNOWN",
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class ToolPin:
    path: str
    sha256: str
    version: str
    commit: str

    def __post_init__(self) -> None:
        if len(self.sha256) != 64 or any(c not in "0123456789abcdef" for c in self.sha256):
            raise ValueError("tool SHA-256 must be lowercase hexadecimal")
        if not self.version.strip() or not self.commit.strip():
            raise ValueError("tool version and source commit are required")


@dataclass(frozen=True)
class RunnerResult:
    status: RunStatus
    query_sha256: str
    proof_sha256: str | None
    cvc5_sha256: str
    logos_sha256: str
    solver_exit_code: int | None
    checker_exit_code: int | None
    solver_stdout: str
    solver_stderr: str
    checker_stdout: str
    checker_stderr: str
    detail: str | None = None
    proof_bytes: bytes | None = None


def _tool_matches_pin(pin: ToolPin) -> bool:
    path = Path(pin.path)
    return path.is_file() and os.access(path, os.X_OK) and sha256_file(path) == pin.sha256


def _first_status_line(output: bytes) -> str | None:
    try:
        lines = output.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return None
    for line in lines:
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def run_cvc5_logos(
    query: bytes,
    cvc5: ToolPin,
    logos: ToolPin,
    *,
    timeout_seconds: float = 30.0,
) -> RunnerResult:
    """Run pinned cvc5 and Logos binaries; return only solver/checker reports.

    A Logos correct result is intentionally named
    CHECKER_REPORTED_CORRECT_UNBOUND. This adapter does not parse and compare
    Logos's assumptions with the canonical LLMLang query AST, and therefore
    cannot issue PROVEN_INDEPENDENCE.
    """
    query_hash = sha256_bytes(query)
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    if not _tool_matches_pin(cvc5):
        return RunnerResult(
            "UNKNOWN", query_hash, None, cvc5.sha256, logos.sha256,
            None, None, "", "", "", "", "cvc5 binary missing or SHA-256 mismatch",
        )
    if not _tool_matches_pin(logos):
        return RunnerResult(
            "UNKNOWN", query_hash, None, cvc5.sha256, logos.sha256,
            None, None, "", "", "", "", "Logos binary missing or SHA-256 mismatch",
        )

    with tempfile.TemporaryDirectory(prefix="llmlang-cpc-proof-") as temp_dir:
        query_path = Path(temp_dir) / "query.smt2"
        proof_path = Path(temp_dir) / "query.smt2.cpc"
        query_path.write_bytes(query)

        solver_command = [
            cvc5.path,
            "--dump-proofs",
            "--proof-format-mode=cpc",
            "--proof-granularity=dsl-rewrite",
            str(query_path),
        ]
        try:
            solver = subprocess.run(
                solver_command,
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return RunnerResult(
                "UNKNOWN", query_hash, None, cvc5.sha256, logos.sha256,
                None, None, "", "", "", "", f"cvc5 execution failed: {type(exc).__name__}",
            )

        solver_stdout = solver.stdout.decode("utf-8", errors="replace")
        solver_stderr = solver.stderr.decode("utf-8", errors="replace")
        if solver.returncode != 0:
            return RunnerResult(
                "UNKNOWN", query_hash, None, cvc5.sha256, logos.sha256,
                solver.returncode, None, solver_stdout, solver_stderr, "", "",
                "cvc5 exited unsuccessfully",
            )

        status_line = _first_status_line(solver.stdout)
        if status_line == "sat":
            return RunnerResult(
                "SOLVER_REPORTED_SAT", query_hash, None, cvc5.sha256, logos.sha256,
                solver.returncode, None, solver_stdout, solver_stderr, "", "",
                "model retrieval and reference replay are not implemented in this adapter",
            )
        if status_line == "unknown":
            return RunnerResult(
                "SOLVER_REPORTED_UNKNOWN", query_hash, None, cvc5.sha256, logos.sha256,
                solver.returncode, None, solver_stdout, solver_stderr, "", "",
                "cvc5 returned unknown",
            )
        if status_line != "unsat":
            return RunnerResult(
                "UNKNOWN", query_hash, None, cvc5.sha256, logos.sha256,
                solver.returncode, None, solver_stdout, solver_stderr, "", "",
                "unrecognized cvc5 output; fail closed",
            )

        # Keep the complete cvc5 output. Logos accepts the CPC proof format
        # emitted by --dump-proofs, including the leading unsat response.
        proof_path.write_bytes(solver.stdout)
        proof_hash = sha256_file(proof_path)
        proof_body = b"\n".join(solver.stdout.splitlines()[1:]).strip()
        if not proof_body:
            return RunnerResult(
                "SOLVER_REPORTED_UNSAT", query_hash, proof_hash, cvc5.sha256, logos.sha256,
                solver.returncode, None, solver_stdout, solver_stderr, "", "",
                "UNSAT response contained no CPC proof body",
            )

        try:
            checker = subprocess.run(
                [logos.path, str(proof_path)],
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return RunnerResult(
                "UNKNOWN", query_hash, proof_hash, cvc5.sha256, logos.sha256,
                solver.returncode, None, solver_stdout, solver_stderr, "", "",
                f"Logos execution failed: {type(exc).__name__}",
            )

        checker_stdout = checker.stdout.decode("utf-8", errors="replace")
        checker_stderr = checker.stderr.decode("utf-8", errors="replace")
        checker_lines = {line.strip() for line in checker_stdout.splitlines()}
        if checker.returncode == 0 and "correct" in checker_lines:
            verdict: RunStatus = "CHECKER_REPORTED_CORRECT_UNBOUND"
            detail = "Logos accepted the proof, but parsed assumptions are not bound to the expected LLMLang query"
        elif checker.returncode == 1 and "incorrect" in checker_lines:
            verdict = "CHECKER_REPORTED_INCORRECT"
            detail = "Logos rejected the CPC derivation"
        elif checker.returncode == 2 and "incomplete" in checker_lines:
            verdict = "CHECKER_REPORTED_INCOMPLETE"
            detail = "Logos accepted the derivation but its soundness side conditions do not apply"
        else:
            verdict = "UNKNOWN"
            detail = "unrecognized Logos response; fail closed"

        return RunnerResult(
            verdict, query_hash, proof_hash, cvc5.sha256, logos.sha256,
            solver.returncode, checker.returncode, solver_stdout, solver_stderr,
            checker_stdout, checker_stderr, detail, solver.stdout,
        )
