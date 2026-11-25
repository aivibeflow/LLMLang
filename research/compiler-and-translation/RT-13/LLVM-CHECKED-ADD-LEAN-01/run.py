#!/usr/bin/env python3
"""Recheck exact Scenario 96A bit-vector predicates with Lean's offline proof route."""

import argparse
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parents[1] / "PROTOTYPES" / "LLVM-PRESERVATION-01"
sys.path.insert(0, str(PRIOR))
import checked_add_replay as prior
from checked_add_formula import Unsupported, conjunction, disagreement, disjunction, form, paths, smt_query
from integer_fixture import SOURCE, compile_source
from llvm_integer_probe import lower

LEAN_COMMIT = "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9"
CORE_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}


def digest(value):
    if isinstance(value, str):
        value = value.encode("utf-8")
    return sha256(value).hexdigest()


def sexpression(predicate):
    tokens = iter(re.findall(r"\(|\)|[^\s()]+", predicate))

    def read(opening):
        if opening == ")":
            raise ValueError("Unexpected close")
        if opening != "(":
            return opening
        children = []
        for token in tokens:
            if token == ")":
                return tuple(children)
            children.append(read(token))
        raise ValueError("Unclosed expression")

    result = read(next(tokens))
    if next(tokens, None) is not None:
        raise ValueError("Trailing expression")
    return result


def bit_literal(value, width):
    return f"({value % 2**width} : BitVec {width})"


def lean_expression(term, names):
    if isinstance(term, str):
        if term in {"true", "false"}:
            return term
        if term in names:
            return names[term]
        raise ValueError(f"Unexpected atom {term!r}")

    match term:
        case ("_", str() as value, str() as width) if value.startswith("bv") and width in {"1", "32", "33"}:
            return bit_literal(int(value[2:]), int(width))
        case (("_", "extract", str() as upper, str() as lower), argument):
            start = int(lower)
            width = int(upper) - start + 1
            return f"(BitVec.extractLsb' {start} {width} {lean_expression(argument, names)})"
        case (("_", "sign_extend", "1"), argument):
            return f"(BitVec.signExtend 33 ({lean_expression(argument, names)} : BitVec 32))"
        case ("not", value):
            return f"(!{lean_expression(value, names)})"
        case ("ite", condition, yes, no):
            return (f"(bif {lean_expression(condition, names)} then {lean_expression(yes, names)} "
                    f"else {lean_expression(no, names)})")
        case (("and" | "or") as operator, *operands) if len(operands) >= 2:
            join = " && " if operator == "and" else " || "
            return "(" + join.join(lean_expression(arg, names) for arg in operands) + ")"
        case (("bvadd" | "=" | "distinct") as operator, left, right):
            symbol = {"bvadd": "+", "=": "==", "distinct": "!="}[operator]
            return f"({lean_expression(left, names)} {symbol} {lean_expression(right, names)})"
        case (("bvslt" | "bvsgt") as operator, left, right):
            if operator == "bvsgt":
                left, right = right, left
            return f"(BitVec.slt {lean_expression(left, names)} {lean_expression(right, names)})"
        case _:
            raise ValueError(f"Unexpected fixed bit-vector expression {term!r}")


def invoke(command, cwd=None, *, timeout=120, allow_fail=False):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                            timeout=timeout, check=False)
    if not allow_fail and (result.returncode or result.stderr):
        raise RuntimeError(result.stdout + result.stderr)
    return result


def shapes(exits):
    guards = [conjunction(*kind.conditions) for kind in exits]
    gaps = form("not", disjunction(*guards))
    overlaps = (conjunction(a, b) for a, b in combinations(guards, 2))
    return {
        "partition": disjunction(gaps, *overlaps),
        "complete_mismatch": disagreement(exits, prior.COMPONENTS),
        "status_and_stores_mismatch": disagreement(exits, ("status", "stores")),
        "status_and_effects_mismatch": disagreement(exits, ("status", "effects")),
    }


def inputs(args):
    archived = json.loads((PRIOR / "checked-add-results.json").read_text(encoding="utf-8"))
    if args.cross_check:
        recreated = prior.replay(args)
        if json.loads(json.dumps(recreated)) != archived:
            raise ValueError("Prior LLVM, solver or native control replay changed")
    source = SOURCE.replace("operation", "checked_sadd")
    ir = lower((compile_source(source),))
    assert prior.digest(source) == archived["source_sha256"]
    assert prior.digest(ir) == archived["unoptimized_ir_sha256"]
    unadmitted = prior.replace_once(ir, "entry:\n", "entry:\n  %unmodeled = add nsw i32 %a, %b\n")
    verified = prior.run([args.opt, "-passes=verify,default<O0>,verify", "-S", "-o", "-", "-"], unadmitted)
    assert prior.digest(verified) == archived["outside_profile"]["ir_sha256"]
    try:
        paths(verified)
    except Unsupported as error:
        assert "add nsw" in str(error)
    else:
        raise AssertionError("LLVM poison promises remain outside the profile")

    goals = {}
    records = {}
    for name, variant in prior.variants(ir).items():
        for level in (0, 3):
            compiled = prior.run([args.opt, f"-passes=verify,default<O{level}>,verify", "-S", "-o", "-", "-"],
                                 variant)
            pinned = archived["modules"][name][f"O{level}"]
            assert prior.digest(compiled) == pinned["ir_sha256"]
            clauses = shapes(paths(compiled))
            hashes = {field: digest(smt_query(predicate)) for field, predicate in clauses.items()}
            assert all(pinned[field]["sha256"] == identity for field, identity in hashes.items())
            record = records[f"{name}_O{level}"] = {
                "ir_sha256": pinned["ir_sha256"], "path_count": pinned["path_count"],
                "query_sha256": hashes,
            }

            included = ["partition"]
            if name == "preserving":
                included.append("complete_mismatch")
            elif name == "reverse_effects":
                included.append("status_and_stores_mismatch")
            elif name == "store_on_error":
                included.append("status_and_effects_mismatch")
            for field in included:
                goals[f"{name}_O{level}_{field}"] = (clauses[field], None, False)
            if name != "preserving":
                witness = tuple(pinned["witness"])
                key = f"{name}_O{level}_witness"
                goals[key] = (clauses["complete_mismatch"], witness, True)
                record["witness"] = {"input": witness, "source": pinned["source_observation"],
                                     "native": pinned["native_observation"]}
    return goals, records, archived


def proposition(name, predicate, witness, holds):
    coding = {name: name for name in ("a", "b", "enabled")}
    if witness is None:
        parameters = "(a b enabled : BitVec 32)"
    else:
        parameters = ""
        coding = {name: bit_literal(value, 32) for name, value in zip(coding, witness, strict=True)}
    expression = lean_expression(sexpression(predicate), coding)
    return f"theorem {name} {parameters} :\n  {expression} = {str(holds).lower()} := by"


def headers(offline):
    prefix = "import Std.Tactic.BVDecide\nset_option linter.unusedVariables false\n"
    if offline:
        prefix += 'set_option sat.solver "/llmlang-fixture-no-solver"\n'
    return prefix + "\n"


def audit(output):
    read = re.compile(r"^'([^']+)' (?:does not depend on any axioms|depends on axioms: \[(.*?)\])$", re.M | re.S)
    reports = {}
    for name, values in read.findall(output):
        axioms = [] if not values else [value.strip() for value in values.split(",")]
        extras = set(axioms) - CORE_AXIOMS
        if any("._native.bv_decide." not in name for name in extras):
            raise ValueError(f"Unexpected proof assumption in {name}")
        reports[name] = axioms
    return reports


def modules(lean, goals, generate=False):
    candidates = {name: proposition(name, *definition) for name, definition in goals.items()}
    synthesis = headers(False) + "\n".join(f"{case}\n  bv_decide?\n" for case in candidates.values())
    archived = HERE / "lrat"
    with TemporaryDirectory(prefix="llmlang-llvm-bitvector-lean-") as directory:
        root = Path(directory)
        source = root / "Generated.lean"
        proof = root / "Offline.lean"
        flags = [lean, "-DwarningAsError=true"]
        if generate:
            source.write_text(synthesis, encoding="utf-8")
            generated = invoke([*flags, str(source)], root).stdout
            suggestions = re.findall(r'\[apply\] (bv_normalize|bv_check "[^\n]+\.lrat")', generated)
            if len(suggestions) != len(candidates):
                raise ValueError(f"Unexpected suggestions for {len(candidates)} goals:\n{generated}")
            archived.mkdir(exist_ok=True)
            for name, tactic in zip(candidates, suggestions, strict=True):
                archive_file = archived / f"{name}.lrat"
                if tactic == "bv_normalize":
                    if archive_file.exists():
                        raise ValueError(f"Unexpected archived proof for normalized goal {name}")
                else:
                    payload = (root / tactic.split('"')[1]).read_bytes()
                    if archive_file.exists():
                        if archive_file.read_bytes() != payload:
                            raise ValueError(f"Regenerated proof differs for {name}")
                    else:
                        archive_file.write_bytes(payload)

        replays = {}
        certificates = {}
        for name in candidates:
            path = f"{name}.lrat"
            archive_file = archived / path
            if archive_file.exists():
                certificate = archive_file.read_bytes()
                (root / path).write_bytes(certificate)
                replays[name] = f'bv_check "{path}"'
                certificates[name] = {"replay": "bv_check", "certificate_sha256": digest(certificate),
                                      "certificate_bytes": len(certificate)}
            else:
                replays[name] = "bv_normalize"
                certificates[name] = {"replay": "bv_normalize"}
        if sum(row["replay"] == "bv_check" for row in certificates.values()) != 12:
            raise ValueError("Expected the twelve pinned LRAT proof artifacts")

        replay = headers(True) + "\n".join(
            f"{declaration}\n  {replays[name]}\n\n#print axioms {name}\n"
            for name, declaration in candidates.items()
        )
        proof.write_text(replay, encoding="utf-8")
        checked = invoke([*flags, str(proof)], root).stdout
        reports = audit(checked)
        assert list(reports) == list(candidates)
        for name, row in certificates.items():
            row["axioms"] = reports[name]
            assert len(set(reports[name]) - CORE_AXIOMS) == (row["replay"] == "bv_check")

        cert = replays["preserving_O0_complete_mismatch"]
        control = root / "Control.lean"
        mismatch, _, _ = goals["drop_overflow_O0_witness"]
        failing = proposition("wrongCertificate", mismatch, None, False)
        control.write_text(headers(True) + f"{failing}\n  {cert}\n", encoding="utf-8")
        rejected = invoke([*flags, str(control)], root, allow_fail=True)
        assert rejected.returncode != 0 and "LRAT" in (rejected.stdout + rejected.stderr)
    return certificates, {"generated_lean": digest(synthesis), "offline_lean": digest(replay)}


def replay(args):
    lean = invoke([args.lean, "--version"]).stdout.strip()
    if LEAN_COMMIT not in lean:
        raise ValueError("Expected pinned Lean 4.36.0")
    goals, records, original = inputs(args)
    certificates, modules_id = modules(args.lean, goals, args.generate_certificates)
    return {
        "schema": "llmlang-llvm-checked-add-lean/1", "lean": lean, "python": platform.python_version(),
        "runner_sha256": digest(Path(__file__).read_bytes()), "modules_sha256": modules_id,
        "tools": original["tools"],
        "prior_ledger_sha256": digest((PRIOR / "checked-add-results.json").read_bytes()),
        "theorems": certificates, "artifacts": records, "outside_profile": original["outside_profile"],
        "replayed_with_unavailable_sat_solver": True, "unrelated_certificate": "refused",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for tool in ("lean", "opt", "llc", "cc", "z3", "cvc5"):
        parser.add_argument(f"--{tool}", default=tool)
    parser.add_argument("--generate-certificates", action="store_true",
                        help="Regenerate pinned LRAT files with Lean and verify their exact bytes")
    parser.add_argument("--cross-check", action="store_true",
                        help="Also reproduce the prior SMT and native control ledger")
    args = parser.parse_args()
    print(json.dumps(replay(args), indent=2))
