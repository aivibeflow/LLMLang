#!/usr/bin/env python3
"""Compare body, implementation declaration and supplied-contract evidence keys."""

from collections import Counter
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
import platform

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "OPERATION-IDENTITY-01" / "evidence.json"
INPUTS = range(256)
PROVIDED = ("general", "parity", "stay", "advance", "permits-mixed", "omits-255")
REQUIRED = ("general", "parity")


def key(domain, value):
    raw = json.dumps((domain, value), separators=(",", ":"), sort_keys=True).encode("ascii")
    return sha256(raw).hexdigest()


def allowed(policy, x):
    stay = (x, "S")
    advance = ((x + 1) % 256, "A")
    if policy == "omits-255" and x == 255:
        return ()
    if policy == "parity":
        return (advance if x % 2 else stay,)
    if policy == "stay":
        return (stay,)
    if policy == "advance":
        return (advance,)
    if policy == "permits-mixed":
        return stay, advance, (x, "A")
    return stay, advance


def refinement(provided, required):
    for x, (source, target) in enumerate(zip(provided, required, strict=True)):
        if target and (not source or not set(source) <= set(target)):
            return x
    return None


def body_check(observations, provided):
    return next((x for x, (observed, declared) in enumerate(zip(observations, provided, strict=True))
                 if declared and observed not in declared), None)


def cases(archive):
    tables = {policy: tuple(allowed(policy, x) for x in INPUTS) for policy in PROVIDED}
    addresses = {policy: key("provided-contract/1", table) for policy, table in tables.items()}
    rows = []
    for native in archive["rows"]:
        if native["context"] != "wrap":
            continue
        executable = native["implementation_hash"]
        observed = list(zip(bytes.fromhex(native["result_bytes_hex"]), native["trace_codes"], strict=True))
        for provided in PROVIDED:
            body_failure = body_check(observed, tables[provided])
            declaration = key("implementation-declaration/1", (executable, addresses[provided]))
            body_key = key("body-judgment/1", (executable, addresses[provided]))
            for required in REQUIRED:
                refine_failure = refinement(tables[provided], tables[required])
                refine_key = key("refinement-judgment/1", (addresses[provided], addresses[required]))
                rows.append({
                    "provider": native["provider"], "provided": provided, "required": required,
                    "body_first_failure": body_failure, "refinement_first_failure": refine_failure,
                    "two_stage_admitted": body_failure is None and refine_failure is None,
                    "direct_first_failure": body_check(observed, tables[required]),
                    "keys": {
                        "executable_and_public": key("executable-public/1", (executable, addresses[required])),
                        "declaration_and_public": key("declaration-public/1", (declaration, addresses[required])),
                        "body_judgment": body_key, "refinement_judgment": refine_key,
                    },
                })
    return addresses, rows


def results():
    source = SOURCE.read_bytes()
    archive = json.loads(source)
    if archive["trace_codebook"] != {"S": ["read", "commit"], "A": ["read", "advance", "commit"],
                                     "R": ["commit", "read"]}:
        raise ValueError("Expected the exact native event model")
    addresses, rows = cases(archive)
    counts = Counter()
    for a, b in combinations(rows, 2):
        for projection, observation in (
            ("executable_and_public", "two_stage_admitted"),
            ("declaration_and_public", "two_stage_admitted"),
            ("body_judgment", "body_first_failure"),
            ("refinement_judgment", "refinement_first_failure"),
        ):
            if a["keys"][projection] == b["keys"][projection] and a[observation] != b[observation]:
                counts[projection] += 1
    if any(row["two_stage_admitted"] and row["direct_first_failure"] is not None for row in rows):
        raise AssertionError("Two-stage admission contradicted the actual body/public outcome")
    summary = {
        name: sum(row[name] is not None for row in rows)
        for name in ("body_first_failure", "refinement_first_failure", "direct_first_failure")
    }
    summary["two_stage_admitted"] = sum(row["two_stage_admitted"] for row in rows)
    summary["direct_pass_and_two_stage_refused"] = sum(
        row["direct_first_failure"] is None and not row["two_stage_admitted"] for row in rows
    )
    return {
        "schema": "llmlang-provided-contract-identity/1", "python": platform.python_version(),
        "native_ledger_sha256": sha256(source).hexdigest(),
        "source_sha256": {name: sha256((HERE / name).read_bytes()).hexdigest()
                          for name in ("run.py", "Admission.lean", "axioms.txt")},
        "contracts": addresses, "cases": rows, "summary": summary,
        "distinct_judgment_pairs_sharing_key": dict.fromkeys(rows[0]["keys"], 0) | dict(counts),
    }


if __name__ == "__main__":
    print(json.dumps(results(), indent=2))
