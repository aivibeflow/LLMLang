"""Check one shared reference and full mutant traces in both native JIT pipelines."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import sys


HERE = Path(__file__).resolve().parent
RT13 = HERE.parent
JIT = RT13 / "cranelift-checked-add"
LLVM = RT13 / "JIT-MATERIALIZATION-01"
sys.path.insert(0, str(JIT))
from run import CHANGED_FIELDS, FIXTURE, SOURCE, cases, compile_source, execute, jit, lower, reference
from checked_add_replay import variants


def digest_rows(rows):
    return sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def parse_llvm(output):
    timing, *results = output.splitlines()
    label, index, value = timing.split()
    if label != "time" or index != "0" or int(value) <= 0:
        raise ValueError(timing)
    rows = []
    for line in results:
        label, status, slot, *effects = line.split()
        if label != "check":
            raise ValueError(line)
        rows.append({"status": int(status), "out_slot": int(slot), "effects": list(map(int, effects))})
    return rows


def replay(args, workspace):
    source = SOURCE.replace("operation", "checked_sadd")
    model = compile_source(source)
    vectors = cases()
    expected = [reference(model, vector) for vector in vectors]
    paths = workspace / "cases.txt"
    paths.write_text("".join(f"{a} {b} {enabled}\n" for a, b, enabled in vectors))
    manifest = {}
    for policy, ir in variants(lower((model,))).items():
        llvm_input = workspace / f"{policy}.ll"
        llvm_input.write_text(ir)
        observations = {
            f"llvm-orc-O{level}": parse_llvm(execute([args.orc, level, 1, llvm_input, paths]))
            for level in (0, 3)
        }
        machine = {"llvm_input_sha256": sha256(llvm_input.read_bytes()).hexdigest()}
        for level in ("none", "speed"):
            rows, artifact = jit(args, workspace, level, policy, vectors)
            profile = f"cranelift-{level}"
            observations[profile] = rows
            machine[profile] = artifact
        shared_rows = next(iter(observations.values()))
        for profile, rows in observations.items():
            if rows != shared_rows:
                raise ValueError((policy, profile, "native observations disagree between engines"))
        projections = Counter()
        first_wrong = None
        differing_fields = set()
        for vector, want, got in zip(vectors, expected, shared_rows, strict=True):
            fields = {field for field in want if want[field] != got[field]}
            if fields:
                differing_fields.update(fields)
                first_wrong = first_wrong or {"input": vector, "reference": want, "actual": got}
                projections["full"] += 1
                for omitted in ("status", "out_slot", "effects"):
                    projections[f"omit-{omitted}"] += bool(fields - {omitted})
        if differing_fields != CHANGED_FIELDS.get(policy, set()):
            raise ValueError((policy, differing_fields))
        manifest[policy] = {
            "common_trace_sha256": digest_rows(shared_rows), "profiles": sorted(observations),
            "different_fields": sorted(differing_fields), "exact_input_or_machine": machine,
            "mismatches": {name: projections[name] for name in ("full", "omit-status", "omit-out_slot", "omit-effects")},
            "first_wrong": first_wrong,
        }
    if manifest["reverse_effects"]["mismatches"]["omit-effects"] or manifest["store_on_error"]["mismatches"]["omit-out_slot"]:
        raise ValueError("weakened projections unexpectedly detected the targeted controls")
    files = (HERE / "run.py", JIT / "run.py", JIT / "Cargo.lock", JIT / "src/main.rs", LLVM / "orc.cpp")
    return {
        "target": "x86_64-unknown-linux-gnu",
        "fixture_source_sha256": sha256(source.encode()).hexdigest(),
        "sources_sha256": {str(path.relative_to(RT13)): sha256(path.read_bytes()).hexdigest() for path in files},
        "oracle_sources_sha256": {name: sha256((FIXTURE / name).read_bytes()).hexdigest()
                                  for name in ("integer_fixture.py", "llvm_integer_probe.py", "checked_add_replay.py")},
        "reference_sha256": digest_rows(expected), "input_sha256": sha256(paths.read_bytes()).hexdigest(),
        "vectors_per_policy_and_profile": len(vectors),
        "tools": {tool: execute([binary, "--version"]).splitlines()[0]
                  for tool, binary in (("llvm", "llvm-config-19"), ("rust", "rustc"), ("gcc", "cc"))},
        "policies": manifest,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--orc", required=True, type=Path)
    parser.add_argument("--probe", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-shared-jit-") as temp:
        data = replay(args, Path(temp))
    args.output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
