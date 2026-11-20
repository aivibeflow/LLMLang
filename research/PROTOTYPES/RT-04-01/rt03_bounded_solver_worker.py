"""One-query SymPy worker with an external wall-clock deadline.

This is an RT-03 experiment, not a production solver service. Each request gets
an isolated process so that a query deadline can terminate an unresponsive
backend without leaving a late result to be confused with a later request.
The protocol currently generates pigeonhole SAT instances only.
"""
from __future__ import annotations

import json
import select
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

from sympy import And, Not, Or, Symbol, false
from sympy.logic.inference import satisfiable


@dataclass(frozen=True)
class BoundedResult:
    status: str
    reason: str | None
    model: dict[str, bool] | None
    request_id: str
    startup_seconds: float
    query_seconds: float
    worker_reaped: bool


def _pigeonhole_formula(pigeons: int, holes: int):
    if pigeons < 1 or holes < 1:
        raise ValueError("pigeons and holes must be positive")
    variables = {
        (p, h): Symbol(f"p{p}_h{h}")
        for p in range(pigeons)
        for h in range(holes)
    }
    clauses = []
    # Every pigeon occupies at least one hole and at most one hole.
    for p in range(pigeons):
        row = [variables[p, h] for h in range(holes)]
        clauses.append(Or(*row))
        clauses.extend(Or(Not(a), Not(b)) for a, b in combinations(row, 2))
    # No two pigeons occupy the same hole.
    for h in range(holes):
        column = [variables[p, h] for p in range(pigeons)]
        clauses.extend(Or(Not(a), Not(b)) for a, b in combinations(column, 2))
    return And(*clauses), tuple(str(v) for v in variables.values())


def _worker_main() -> int:
    # Imports are complete before READY, so the query timer excludes cold import.
    print(json.dumps({"kind": "ready", "protocol": 1}), flush=True)
    for line in sys.stdin:
        request_id = None
        try:
            request = json.loads(line)
            request_id = request["request_id"]
            formula, names = _pigeonhole_formula(
                int(request["pigeons"]), int(request["holes"])
            )
            result = satisfiable(formula, algorithm="dpll2")
            if result is false or result is False:
                response = {"request_id": request_id, "status": "unsat"}
            else:
                model = {
                    str(symbol): bool(value)
                    for symbol, value in result.items()
                    if str(symbol) in names and value in (True, False)
                }
                response = {
                    "request_id": request_id,
                    "status": "sat",
                    "model": model,
                }
        except Exception as exc:  # protocol returns failure, never an UNSAT claim
            response = {
                "request_id": request_id,
                "status": "error",
                "reason": type(exc).__name__,
            }
        print(json.dumps(response, sort_keys=True), flush=True)
    return 0


def _readline_until(stream, process, deadline: float) -> str | None:
    while time.monotonic() < deadline:
        remaining = max(0.0, deadline - time.monotonic())
        ready, _, _ = select.select([stream], [], [], min(remaining, 0.05))
        if ready:
            return stream.readline()
        if process.poll() is not None:
            return None
    return None


def run_pigeonhole_query(
    pigeons: int,
    holes: int,
    timeout_seconds: float,
    *,
    startup_timeout_seconds: float = 10.0,
) -> BoundedResult:
    """Run one query; every incomplete or malformed outcome becomes UNKNOWN."""
    if pigeons < 1 or holes < 1:
        raise ValueError("pigeons and holes must be positive")
    if timeout_seconds <= 0 or startup_timeout_seconds <= 0:
        raise ValueError("timeouts must be positive")

    request_id = uuid.uuid4().hex
    worker_file = Path(__file__).resolve()
    process = subprocess.Popen(
        [sys.executable, "-u", str(worker_file), "--worker"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    start = time.monotonic()
    ready_line = _readline_until(process.stdout, process, start + startup_timeout_seconds)
    startup_seconds = time.monotonic() - start
    query_start = time.monotonic()
    status, reason, model = "unknown", "worker_startup_timeout", None
    try:
        ready = json.loads(ready_line) if ready_line else None
        if not isinstance(ready, dict) or ready != {"kind": "ready", "protocol": 1}:
            if process.poll() is None:
                reason = "worker_protocol_error"
            else:
                reason = "worker_crashed_before_ready"
        else:
            process.stdin.write(json.dumps({
                "request_id": request_id,
                "pigeons": pigeons,
                "holes": holes,
            }) + "\n")
            process.stdin.flush()
            line = _readline_until(process.stdout, process, query_start + timeout_seconds)
            if line is None:
                reason = "timeout" if process.poll() is None else "worker_crashed"
            else:
                try:
                    response = json.loads(line)
                except json.JSONDecodeError:
                    response = None
                if not isinstance(response, dict):
                    reason = "malformed_response"
                elif response.get("request_id") != request_id:
                    reason = "request_id_mismatch"
                elif response.get("status") in {"sat", "unsat"}:
                    status = response["status"]
                    model = response.get("model") if status == "sat" else None
                    reason = None
                else:
                    reason = response.get("reason", "worker_error")
    except (BrokenPipeError, OSError, ValueError, TypeError):
        reason = "worker_protocol_error"
    finally:
        if process.poll() is None:
            process.kill()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            reason = "worker_not_reaped"
            status, model = "unknown", None
        for stream in (process.stdin, process.stdout):
            if stream is not None:
                stream.close()

    return BoundedResult(
        status=status,
        reason=reason,
        model=model,
        request_id=request_id,
        startup_seconds=startup_seconds,
        query_seconds=time.monotonic() - query_start,
        worker_reaped=process.poll() is not None,
    )


if __name__ == "__main__":
    if sys.argv[1:] == ["--worker"]:
        raise SystemExit(_worker_main())
    outcome = run_pigeonhole_query(10, 9, 0.5)
    print(json.dumps(outcome.__dict__, sort_keys=True, indent=2))
