"""Compare reference and verified native process observations with the RT-01 corpus."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import runpy
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory

from .__main__ import FIXTURES, TARGET, WORKLOADS, stage0_compiler
from .review import public_key_id


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "research/language-design/PROTOTYPES/CLI-WORKLOADS-01/run.py"
EXCLUSIONS = ["Calculator tokens split across LF and trailing records are outside the RT-01 corpus."]


def _output(command):
    return subprocess.run(
        command, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, timeout=60,
    ).stdout.strip()


def _test_approval(cli, directory):
    reviewer = "RT-01 test reviewer"
    key = directory / "conformance-private.pem"
    public_key = directory / "conformance-public.pem"
    policy = directory / "conformance-policy.json"
    receipt = directory / "conformance-receipt.json"
    subprocess.run(
        ["openssl", "genpkey", "-algorithm", "ED25519", "-out", str(key)],
        check=True, timeout=60,
    )
    subprocess.run(
        ["openssl", "pkey", "-in", str(key), "-pubout", "-out", str(public_key)],
        check=True, timeout=60,
    )
    policy.write_text(json.dumps({
        "schema": "llmlang-review-policy/v1",
        "reviewer": reviewer,
        "public_key": public_key.name,
        "public_key_id": public_key_id(public_key),
    }) + "\n", encoding="utf-8")
    line = _output([*cli, "review"]).rpartition("\n")[2]
    label, separator, packet = line.partition(": ")
    if label != "Review packet" or not separator or not packet:
        raise ValueError("review did not print a packet identity")
    subprocess.run(
        [*cli, "approve-review", "--packet", packet, "--reviewer", reviewer,
         "--signing-key", str(key), "-o", str(receipt)],
        check=True, timeout=60,
    )
    return receipt, policy


def _hex(data):
    return None if data is None else data.hex()


def _observe(command, case, run_case):
    try:
        process = run_case(command, case)
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"error": str(error)}
    return {
        "exit_status": process.returncode,
        "stdout_hex": _hex(process.stdout),
        "stderr_hex": _hex(process.stderr),
    }


def _differences(observation, case):
    if "error" in observation:
        return [observation["error"]]
    status = observation["exit_status"]
    accepted = status == 0 if case.success else (
        status > 0 or (case.broken_stdout and status == -signal.SIGPIPE)
    )
    differences = []
    if not accepted:
        differences.append(f"unexpected status {status}")
    for stream in ("stdout", "stderr"):
        expected = getattr(case, stream)
        actual = observation[f"{stream}_hex"]
        if expected is not None and _hex(expected) != actual:
            differences.append(f"{stream} bytes {actual} (hex), expected {expected.hex()}")
    return differences


def _compare(cases, run_case, reference, native):
    results = []
    for case in cases:
        interpreter = _observe(reference[case.program], case, run_case)
        executable = _observe(native[case.program], case, run_case)
        problems = [
            f"{backend}: {difference}"
            for backend, observation in (("interpreter", interpreter), ("native", executable))
            for difference in _differences(observation, case)
        ]
        if not problems and interpreter != executable:
            problems.append(f"interpreter and native observations differ: {interpreter} vs {executable}")
        status = "PASS" if not problems else "FAIL"
        detail = f" ({', '.join(problems)})" if problems else ""
        print(f"{status} {case.identifier}{detail}")
        results.append({
            "case": case.identifier,
            "workload": case.program,
            "argv_hex": [os.fsencode(argument).hex() for argument in case.argv],
            "stdin_hex": case.stdin.hex(),
            "broken_stdout": case.broken_stdout,
            "expected": {
                "success": case.success,
                "stdout_hex": _hex(case.stdout),
                "stderr_hex": _hex(case.stderr),
            },
            "interpreter": interpreter,
            "native": executable,
            "problems": problems,
        })
    return results


def _digest(path):
    return f"sha256:{sha256(path.read_bytes()).hexdigest()}"


def _check_spg_reconstruction(cli):
    command = [*cli, "show-spg"]
    graph = subprocess.check_output(command, timeout=60)
    if graph != subprocess.check_output(command, timeout=60):
        raise ValueError("canonical SPG differs between repeated frontend runs")
    canonical = json.dumps(json.loads(graph), sort_keys=True, separators=(",", ":"))
    return f"sha256:{sha256(canonical.encode('utf-8')).hexdigest()}"


def _check_admission(cli, tool_args, directory, receipt, policy, spg):
    source = (FIXTURES / "calculator.llmlang").read_bytes()
    copy = directory / "calculator-copy.llmlang"
    copy.write_bytes(source)
    revised = directory / "calculator-revised.llmlang"
    revised.write_bytes(source + b"\n# Revision changes while the SPG remains the same.\n")
    revised_cli = [*cli, "--source", str(revised)]
    if _check_spg_reconstruction(revised_cli) != spg:
        raise ValueError("the review staleness control must preserve the canonical SPG")

    damaged = directory / "damaged-receipt.json"
    decision = json.loads(receipt.read_bytes())
    signature = bytes.fromhex(decision["signature"])
    decision["signature"] = (bytes([signature[0] ^ 1]) + signature[1:]).hex()
    damaged.write_text(json.dumps(decision), encoding="utf-8")

    receipt_args = ["--review-receipt", str(receipt)]
    policy_args = ["--review-policy", str(policy)]
    build = [*tool_args, "build"]
    controls = (
        ("missing review policy", [*cli, *build, *receipt_args],
         "requires --review-policy and --review-receipt", None),
        ("tampered signature", [*cli, *build, *policy_args, "--review-receipt", str(damaged)],
         "review signature verification failed", b"existing output\n"),
        ("stale source revision", [*revised_cli, *build, *receipt_args, *policy_args],
         "does not approve the exact packet", b"existing output\n"),
    )
    checks = []
    for index, (name, command, expected_error, previous) in enumerate(controls):
        output = directory / f"rejected-output-{index}"
        if previous is not None:
            output.write_bytes(previous)
        result = subprocess.run(
            [*command, "-o", str(output)], capture_output=True, text=True, timeout=60,
        )
        remaining = output.read_bytes() if output.exists() else None
        if result.returncode != 1 or expected_error not in result.stderr or remaining != previous:
            raise ValueError(f"review admission control failed for {name}: {result.stderr.strip()}")
        checks.append({"case": name, "exit_status": result.returncode,
                       "diagnostic": result.stderr.strip(), "output_unchanged": True})
        print(f"PASS review admission rejects {name} without changing output")
    return copy, checks


def _report(args, stage0, spg, native, receipt, policy, admission, results):
    decision = json.loads(receipt.read_bytes())
    return {
        "schema": "llmlang-rt01-conformance/v1",
        "target": {"os": platform.system(), "arch": platform.machine(), "triple": TARGET},
        "tools": {
            "python": platform.python_version(),
            "rustc": _output([args.rustc, "--version", "--verbose"]),
            "boogie": _output([args.boogie, "/version"]),
            "z3": _output([args.z3, "--version"]),
            "openssl": _output(["openssl", "version"]),
            "stage0": {"version": _output([str(stage0), "--version"]), "binary": _digest(stage0)},
        },
        "inputs": {
            str(path.relative_to(ROOT)): _digest(path)
            for path in (RUNNER, FIXTURES / "calculator.llmlang",
                         FIXTURES / "calculator.contracts.json", FIXTURES / "calculator.scenarios.json")
        },
        "spg": spg,
        "review": {
            "packet": decision["packet"],
            "public_key_id": decision["public_key_id"],
            "receipt": _digest(receipt),
            "policy": _digest(policy),
            "policy_origin": "external" if args.review_receipt is not None else "ephemeral test policy",
        },
        "native_executables": {name: _digest(Path(command[0])) for name, command in native.items()},
        "review_admission_controls": admission,
        "exclusions": EXCLUSIONS,
        "passed": sum(not result["problems"] for result in results),
        "total": len(results),
        "cases": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boogie", default="boogie")
    parser.add_argument("--z3", default="z3")
    parser.add_argument("--rustc", default="rustc")
    parser.add_argument("--stage0", type=Path)
    parser.add_argument("--review-receipt", type=Path)
    parser.add_argument("--review-policy", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if (args.review_receipt is None) != (args.review_policy is None):
        parser.error("provide both --review-receipt and --review-policy")

    try:
        corpus = runpy.run_path(str(RUNNER))
        stage0 = Path(stage0_compiler(args.stage0)).resolve()
        cli = [sys.executable, "-B", "-m", "draft.llmlang_mvp", "--stage0", str(stage0)]
        spg = _check_spg_reconstruction(cli)
        print(f"Canonical SPG reproduced {spg}")
        with TemporaryDirectory(prefix="llmlang-mvp-conformance-") as temporary:
            directory = Path(temporary)
            receipt, policy = ((args.review_receipt, args.review_policy) if args.review_receipt
                               else _test_approval(cli, directory))
            tool_args = ["--boogie", args.boogie, "--z3", args.z3]
            source_copy, admission = _check_admission(cli, tool_args, directory, receipt, policy, spg)
            adapters = [*cli, "--source", str(directory / "absent.llmlang"),
                        "--contracts", str(directory / "absent.contracts.json")]
            calculator = [*cli, "--source", str(source_copy)]
            workload_cli = {name: calculator if name == "calculator" else adapters for name in WORKLOADS}
            reference = {
                name: [*workload_cli[name], "run", "--workload", name, "--"] for name in WORKLOADS
            }
            native = {}
            for workload in WORKLOADS:
                output = str(directory / workload)
                review = (["--review-receipt", str(receipt), "--review-policy", str(policy)]
                          if workload == "calculator" else [])
                subprocess.run(
                    [*workload_cli[workload], *tool_args,
                     "build", "--rustc", args.rustc, "--workload", workload, "-o", output, *review],
                    check=True, timeout=300,
                )
                native[workload] = [output]
            admission.append({"case": "byte-identical source copy", "exit_status": 0})
            print("PASS review admission accepts a byte-identical source copy")
            results = _compare(corpus["CASES"], corpus["run_case"], reference, native)
            if args.report is not None:
                report = _report(args, stage0, spg, native, receipt, policy, admission, results)
                args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"llmlang conformance: {error}\n")

    passed = sum(not result["problems"] for result in results)
    print(f"{passed}/{len(results)} passed in both backends with exact observations")
    print(*EXCLUSIONS, sep="\n")
    return int(passed != len(results))


if __name__ == "__main__":
    sys.exit(main())
