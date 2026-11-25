"""Check, review, interpret, or compile the LLMLang scalar MVP."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from . import contract, frontend, native, runtime, verify


FIXTURES = Path(__file__).resolve().parent
WORKLOADS = ("calculator", "hello", "echo")


def load_program(source, contracts):
    source_bytes = source.read_bytes()
    contract_bytes = contracts.read_bytes()
    definitions = contract.parse_contracts(contract_bytes.decode("utf-8"))
    hashes = {
        name: contract.contract_hash(pair["provided"])
        for name, pair in definitions.items()
    }
    program = frontend.parse(
        source_bytes.decode("utf-8"), provided_contract_hashes=hashes
    )
    inputs = {str(source): sha256(source_bytes).hexdigest(),
              str(contracts): sha256(contract_bytes).hexdigest()}
    return program, definitions, inputs


def review_packet(program, definitions, inputs):
    graph = json.dumps(program, sort_keys=True, separators=(",", ":")).encode("utf-8")
    lines = [
        f"SPG snapshot: sha256:{sha256(graph).hexdigest()}",
        *(f"Input: {path} — sha256:{digest}" for path, digest in inputs.items()),
        "Scope: scalar function outcomes and declared input domains.",
        "CLI and native I/O behavior is evaluated by conformance tests.",
    ]
    for name, pair in sorted(definitions.items()):
        lines.append(f"{name} — {program['functions'][name]['impl_hash']}")
        for role in ("public", "provided"):
            value = pair[role]
            lines.append(f"  {role} — {contract.contract_hash(value)}")
            lines.append(contract.checked_render(value))
    return "\n".join(lines) + "\n"


def packet_id(packet):
    return "sha256:" + sha256(packet.encode("utf-8")).hexdigest()


def verify_review_receipt(path, expected):
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(receipt, dict)
        or receipt.get("schema") != "llmlang-local-review/v1"
        or receipt.get("packet") != expected
        or receipt.get("decision") != "approved"
        or not isinstance(receipt.get("reviewer"), str)
        or not receipt["reviewer"].strip()
    ):
        raise ValueError("review receipt does not approve the exact current packet")


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


def compile_native(program, workload, rustc, output):
    generated = native.emit_rust(program, workload)
    output = output.absolute()
    with TemporaryDirectory(prefix=".llmlang-build-", dir=output.parent) as directory:
        source = Path(directory) / "main.rs"
        executable = Path(directory) / "program"
        source.write_text(generated, encoding="utf-8")
        subprocess.run(
            [rustc, "--edition=2021", "-O", str(source), "-o", str(executable)],
            check=True,
            timeout=60,
        )
        executable.replace(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=FIXTURES / "calculator.llmlang")
    parser.add_argument("--contracts", type=Path, default=FIXTURES / "calculator.contracts.json")
    parser.add_argument("--boogie", default="boogie")
    parser.add_argument("--z3")
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("show-spg")
    actions.add_parser("review")
    actions.add_parser("check")
    approve = actions.add_parser("approve-review")
    approve.add_argument("--packet", required=True)
    approve.add_argument("--reviewer", required=True)
    approve.add_argument("-o", "--output", type=Path, required=True)
    run = actions.add_parser("run")
    run.add_argument("--workload", choices=WORKLOADS, default="calculator")
    run.add_argument("arguments", nargs=argparse.REMAINDER)
    build = actions.add_parser("build")
    build.add_argument("--workload", choices=WORKLOADS, default="calculator")
    build.add_argument("--rustc", default="rustc")
    build.add_argument("--review-receipt", type=Path)
    build.add_argument("-o", "--output", type=Path, required=True)
    arguments = parser.parse_args()

    try:
        program, definitions, inputs = load_program(arguments.source, arguments.contracts)
        if arguments.action == "show-spg":
            print(json.dumps(program, sort_keys=True, indent=2))
            return 0
        if arguments.action in ("review", "approve-review"):
            packet = review_packet(program, definitions, inputs)
            identity = packet_id(packet)
            if arguments.action == "review":
                print(packet, end="")
                print(f"Review packet: {identity}")
            else:
                if arguments.packet != identity or not arguments.reviewer.strip():
                    raise ValueError("provide the current review packet identity and a reviewer")
                with arguments.output.open("x", encoding="utf-8") as stream:
                    json.dump({
                        "schema": "llmlang-local-review/v1",
                        "packet": identity,
                        "decision": "approved",
                        "reviewer": arguments.reviewer,
                    }, stream, indent=2)
                    stream.write("\n")
            return 0
        if arguments.action == "run":
            rest = arguments.arguments
            if rest[:1] == ["--"]:
                rest = rest[1:]
            return execute(arguments.workload, program, rest)

        if arguments.action == "build" and arguments.review_receipt is not None:
            verify_review_receipt(
                arguments.review_receipt, packet_id(review_packet(program, definitions, inputs))
            )
        if arguments.action == "build" and arguments.workload == "calculator":
            for name in ("add", "sub", "mul", "div"):
                if name not in definitions or definitions[name]["public"].requires:
                    raise ValueError(f"Calculator requires a total public input domain for {name}")

        evidence = verify.verify(
            program, definitions, boogie=arguments.boogie, z3=arguments.z3
        )
        evidence["inputs"] = inputs
        if arguments.action == "check" or evidence["status"] != "VERIFIED":
            print(json.dumps(evidence, sort_keys=True, indent=2))
        if evidence["status"] != "VERIFIED":
            return 1
        if arguments.action == "build":
            compile_native(program, arguments.workload, arguments.rustc, arguments.output)
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"llmlang: {exc}\n")


if __name__ == "__main__":
    sys.exit(main())
