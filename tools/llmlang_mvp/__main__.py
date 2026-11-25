"""Check, review, interpret, or compile the LLMLang scalar MVP."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from . import contract, contract_wire, frontend, review, runtime, verify


FIXTURES = Path(__file__).resolve().parent
WORKLOADS = ("calculator", "hello", "echo")
TARGET = "x86_64-unknown-linux-gnu"
STAGE0_MANIFEST = FIXTURES / "stage0" / "Cargo.toml"


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def binding_manifest(program, definitions):
    functions = program["functions"]
    manifest = {}
    for name, function in sorted(functions.items()):
        public = contract.contract_hash(definitions[name]["public"])
        interface = {"name": name, "public_contract_hash": public}
        manifest[name] = {
            "interface_revision": "sha256:" + sha256(
                b"LLMLang scalar interface v1\0" + canonical_json(interface).encode("utf-8")
            ).hexdigest(),
            "public_contract_hash": public,
            "provided_contract_hash": function["provided_contract_hash"],
            "impl_hash": function["impl_hash"],
            "calls": {
                callee: {
                    "required_contract_hash": contract.contract_hash(definitions[callee]["public"]),
                    "impl_hash": functions[callee]["impl_hash"],
                }
                for callee in sorted(set(verify.reachable_callees(function["body"])))
            },
        }
    return {"schema": "llmlang-scalar-binding/v1", "functions": manifest}


def stage0_compiler(executable):
    """Find the requested compiler or build the checkout with its lockfile."""
    if executable is not None:
        return Path(executable).resolve(strict=True)
    completed = subprocess.run(
        ["cargo", "build", "--manifest-path", str(STAGE0_MANIFEST), "--locked", "--offline",
         "--message-format=json"],
        stdout=subprocess.PIPE, text=True, timeout=300,
    )
    binary = None
    for line in completed.stdout.splitlines():
        message = json.loads(line)
        if message.get("reason") == "compiler-message":
            rendered = message["message"].get("rendered")
            if rendered:
                sys.stderr.write(rendered)
        if (message.get("reason") == "compiler-artifact" and message.get("executable")
                and message["target"]["name"] == "llmlang-stage0"):
            binary = Path(message["executable"])
    completed.check_returncode()
    if binary is not None:
        return binary
    raise ValueError("Cargo did not report the Stage 0 compiler executable")


def load_program(source, contracts, stage0=None):
    source_bytes = source.read_bytes()
    contract_bytes = contracts.read_bytes()
    definitions, pointer_prefix = contract_wire.load_document(contract_bytes.decode("utf-8"))
    hashes = {
        name: contract.contract_hash(pair["provided"])
        for name, pair in definitions.items()
    }
    reference = frontend.parse(
        source_bytes.decode("utf-8"), provided_contract_hashes=hashes
    )
    program = reference
    if stage0 is not None:
        with TemporaryDirectory(prefix="llmlang-lower-") as directory:
            snapshot = Path(directory)
            source_file = snapshot / "source.llmlang"
            hashes_file = snapshot / "contracts.json"
            source_file.write_bytes(source_bytes)
            hashes_file.write_text(canonical_json(hashes), encoding="utf-8")
            result = subprocess.run(
                [stage0, "lower", source_file, hashes_file],
                check=True, stdout=subprocess.PIPE, text=True, timeout=60,
            )
        program = json.loads(result.stdout)
        if canonical_json(program) != canonical_json(reference):
            raise ValueError("Stage 0 and the reference frontend disagree on the canonical SPG")
    inputs = {
        "source": sha256(source_bytes).hexdigest(),
        "contracts": sha256(contract_bytes).hexdigest(),
    }
    return program, definitions, inputs, pointer_prefix


def check_review_policy(path, receipt, packet):
    policy = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=contract._unique_pairs)
    if (not isinstance(policy, dict)
            or policy.keys() != {"schema", "reviewer", "public_key", "public_key_id"}
            or policy["schema"] != "llmlang-review-policy/v1"
            or any(not isinstance(policy[field], str) or not policy[field].strip()
                   for field in ("reviewer", "public_key", "public_key_id"))
            or not frontend.HASH.fullmatch(policy["public_key_id"])):
        raise ValueError("invalid trusted review policy")
    public_key = path.parent / policy["public_key"]
    review.verify_review_receipt(
        receipt, packet, policy["reviewer"], public_key, key_id=policy["public_key_id"]
    )


def execute(workload, program, arguments):
    if workload == "hello":
        status, output, errors = 0, b"Hello, world!\n", b""
    elif workload == "echo":
        status, output, errors = 0, b" ".join(map(os.fsencode, arguments)) + b"\n", b""
    else:
        status, output, errors = runtime.run_calculator(program, sys.stdin.buffer.readline())
    try:
        sys.stdout.buffer.write(output)
        sys.stdout.buffer.flush()
        sys.stderr.buffer.write(errors)
        sys.stderr.buffer.flush()
    except BrokenPipeError:
        with open(os.devnull, "wb") as sink:
            os.dup2(sink.fileno(), sys.stdout.fileno())
        return 1
    return status


def validate_calculator(program, definitions, *, require_total=False):
    for name in ("add", "sub", "mul", "div"):
        value = program["functions"].get(name)
        if (value is None or value["result"] != "i64"
                or [typ for _, typ in value["params"]] != ["i64", "i64"]):
            raise ValueError(f"Calculator requires {name}(I64, I64) -> I64")
        if require_total and definitions[name]["public"].requires:
            raise ValueError(f"Calculator requires a total public input domain for {name}")


def compile_native(program, workload, stage0, rustc, output):
    generated = subprocess.run(
        [stage0, "emit-rust", workload], input=canonical_json(program),
        check=True, stdout=subprocess.PIPE, text=True, timeout=60,
    ).stdout
    output = output.absolute()
    with TemporaryDirectory(prefix=".llmlang-build-", dir=output.parent) as directory:
        source = Path(directory) / "main.rs"
        executable = Path(directory) / "program"
        source.write_text(generated, encoding="utf-8")
        subprocess.run(
            [rustc, "--edition=2021", "--target", TARGET, "-O", str(source), "-o", str(executable)],
            check=True,
            timeout=60,
        )
        executable.replace(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=FIXTURES / "calculator.llmlang")
    parser.add_argument("--contracts", type=Path, default=FIXTURES / "calculator.contracts.json")
    parser.add_argument("--scenarios", type=Path)
    parser.add_argument("--previous-contracts", type=Path)
    parser.add_argument("--stage0", type=Path)
    parser.add_argument("--boogie", default="boogie")
    parser.add_argument("--z3")
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("show-spg")
    actions.add_parser("export-contract-ir")
    actions.add_parser("review")
    actions.add_parser("check")
    key_id = actions.add_parser("review-key-id")
    key_id.add_argument("public_key", type=Path)
    approve = actions.add_parser("approve-review")
    approve.add_argument("--packet", required=True)
    approve.add_argument("--reviewer", required=True)
    approve.add_argument("--signing-key", type=Path, required=True)
    approve.add_argument("-o", "--output", type=Path, required=True)
    run = actions.add_parser("run")
    run.add_argument("--workload", choices=WORKLOADS, default="calculator")
    run.add_argument("arguments", nargs=argparse.REMAINDER)
    build = actions.add_parser("build")
    build.add_argument("--workload", choices=WORKLOADS, default="calculator")
    build.add_argument("--rustc", default="rustc")
    build.add_argument("--review-receipt", type=Path)
    build.add_argument("--review-policy", type=Path)
    build.add_argument("-o", "--output", type=Path, required=True)
    arguments = parser.parse_args()

    try:
        action = arguments.action
        if action == "review-key-id":
            print(review.public_key_id(arguments.public_key))
            return 0
        if action == "export-contract-ir":
            definitions = contract_wire.loads(arguments.contracts.read_text(encoding="utf-8"))
            print(contract_wire.dumps(definitions), end="")
            return 0
        if action == "run" and arguments.workload != "calculator":
            program = None
        elif action == "build" and arguments.workload != "calculator":
            if arguments.review_receipt or arguments.review_policy:
                raise ValueError("review applies to the Calculator scalar program")
            stage0 = stage0_compiler(arguments.stage0)
            compile_native(None, arguments.workload, stage0, arguments.rustc, arguments.output)
            return 0
        else:
            stage0 = None if action == "run" else stage0_compiler(arguments.stage0)
            program, definitions, inputs, pointer_prefix = load_program(
                arguments.source, arguments.contracts, stage0
            )

        if action == "run":
            if arguments.workload == "calculator":
                validate_calculator(program, definitions)
            rest = arguments.arguments
            if rest[:1] == ["--"]:
                rest = rest[1:]
            return execute(arguments.workload, program, rest)
        if action == "show-spg":
            print(json.dumps(program, sort_keys=True, indent=2))
            return 0
        if action in {"review", "approve-review", "build"}:
            packet = review.review_packet(
                program, definitions, inputs, contract_input="contracts",
                contract_pointer_prefix=pointer_prefix,
                scenarios_path=arguments.scenarios, require_pass=action != "review",
                previous_contracts_path=arguments.previous_contracts,
            )
            identity = review.packet_id(packet)
            if action == "review":
                print(packet, end="")
                print(f"Review packet: {identity}")
                return 0
            if action == "approve-review":
                if arguments.packet != identity:
                    raise ValueError("provide the current review packet identity")
                review.write_review_receipt(
                    arguments.output, identity, arguments.reviewer, arguments.signing_key
                )
                return 0
            if arguments.review_policy is None or arguments.review_receipt is None:
                raise ValueError("Calculator build requires --review-policy and --review-receipt")
            check_review_policy(arguments.review_policy, arguments.review_receipt, identity)
            validate_calculator(program, definitions, require_total=True)

        evidence = verify.verify(program, definitions, boogie=arguments.boogie, z3=arguments.z3)
        evidence["inputs"] = inputs
        evidence["spg_sha256"] = sha256(canonical_json(program).encode("utf-8")).hexdigest()
        evidence["binding"] = binding_manifest(program, definitions)
        if action == "check" or evidence["status"] != "VERIFIED":
            print(json.dumps(evidence, sort_keys=True, indent=2))
        if evidence["status"] != "VERIFIED":
            return 1
        if action == "build":
            compile_native(program, arguments.workload, stage0, arguments.rustc, arguments.output)
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"llmlang: {exc}\n")


if __name__ == "__main__":
    sys.exit(main())
