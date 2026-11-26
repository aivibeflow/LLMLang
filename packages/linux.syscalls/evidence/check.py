"""Check the modeled Linux scalar return envelope and replay native boundary cases."""

import argparse
from hashlib import file_digest
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess


MODULE = Path(__file__).resolve()
ROOT = MODULE.parents[3]
BOOGIE_MODEL = MODULE.with_name("return_envelope.bpl").relative_to(ROOT)
LEAN_MODEL = MODULE.with_name("ReturnEnvelope.lean").relative_to(ROOT)
SCHEMA = "llmlang.linux.syscalls.return-envelope-evidence.v1"
TOOLS = {
    "boogie": ("/version", r"version 3\.5\.5\.0\b"),
    "z3": ("--version", r"version 4\.13\.3\b"),
    "lean": ("--version", r"version 4\.36\.0\b"),
}
OBLIGATIONS = {
    "decoder_body_conformance": "decode",
    "public_contract_refinement": "refine",
}
CONTROLS = {
    "errno_as_progress": {
        "procedure": "rejectErrnoAsProgress", "operation": "read", "raw": -4,
        "requested": 5, "proposed": "progress 4", "expected": "errno 4",
    },
    "missing_kernel_assumption": {
        "procedure": "rejectMissingKernelAssumption", "operation": "read", "raw": -4096,
        "requested": 5, "proposed": "public outcome", "expected": "abi_violation -4096",
    },
}


def digest(path):
    with open(path, "rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def run(command, timeout):
    try:
        with subprocess.Popen(
            command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, start_new_session=True,
        ) as process:
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.communicate()
                return {"status": "UNKNOWN", "diagnostic": "command deadline exceeded"}
    except (OSError, ValueError) as exc:
        return {"status": "ERROR", "diagnostic": str(exc)}
    return {"returncode": process.returncode, "stdout": stdout, "stderr": stderr}


def tool(name, executable, timeout):
    found = shutil.which(executable)
    if not found:
        return {"status": "ERROR", "diagnostic": f"{name} executable required"}
    path = str(Path(found).absolute())
    flag, expected_version = TOOLS[name]
    result = run([path, flag], timeout)
    if "status" in result:
        return result
    output = result["stdout"] + result["stderr"]
    if result["returncode"] or not re.search(expected_version, output):
        return {"status": "ERROR", "diagnostic": f"unexpected {name} version: {output.strip()}"}
    return {"status": "READY", "path": path, "version": output.strip(), "sha256": digest(path)}


def boogie_check(tools, procedure, timeout, *, negative=False):
    command = [
        tools["boogie"]["path"], "/proverOpt:SOLVER=z3",
        f"/proverOpt:PROVER_PATH={tools['z3']['path']}", "/proverWarnings:1",
        f"/proc:{procedure}", str(BOOGIE_MODEL),
    ]
    result = run(command, timeout)
    if "status" in result:
        return dict(result, command=command)
    output = (result["stdout"] + result["stderr"]).strip()
    summary = re.search(r"finished with (\d+) verified, (\d+) errors?", output)
    if re.search(r"timed out|out of (?:resources?|memory)|inconclusive", output, re.I):
        status = "UNKNOWN"
    elif (result["returncode"] or not summary
          or re.search(r"prover (?:error|warning)|fatal error|internal error", output, re.I)):
        status = "ERROR"
    elif not negative and summary.groups() == ("1", "0"):
        status = "MODEL_CHECKED"
    elif (negative and summary.groups() == ("0", "1")
          and "a postcondition could not be proved on this return path" in output):
        status = "MODEL_CONTROL_REJECTED"
    else:
        status = "ERROR"
    return {"status": status, "command": command, "diagnostic": output}


def lean_check(executable, timeout):
    command = [executable, "-DwarningAsError=true", str(LEAN_MODEL)]
    result = run(command, timeout)
    if "status" in result:
        return dict(result, command=command)
    return {
        "status": "ERROR" if result["returncode"] else "MODEL_CHECKED",
        "command": command,
        "diagnostic": (result["stdout"] + result["stderr"]).strip(),
        "theorems": [
            "LinuxSyscalls.decoderConformance", "LinuxSyscalls.publicRefinement",
            "LinuxSyscalls.decodedPublicOutcome",
        ],
    }


def reference_outcome(operation, raw, count):
    if -4095 <= raw < 0:
        return f"errno {-raw}"
    if not 0 <= raw <= count:
        return f"abi_violation {raw}"
    if operation == "read" and raw == 0 and count > 0:
        return "eof"
    return f"progress {raw}"


def replay_decoder(executable, timeout):
    path = Path(executable).resolve()
    if not path.is_file():
        return {"status": "ERROR", "diagnostic": "native decoder executable required"}
    cases = []
    for operation in ("read", "write"):
        for count in (0, 1, 5, 2**63 - 1):
            values = {-2**63, -4096, -4095, -38, -4, -1, 0, 1, count, 2**63 - 1}
            if count < 2**63 - 1:
                values.add(count + 1)
            for raw in sorted(values):
                expected = reference_outcome(operation, raw, count)
                response = run([str(path), operation, str(raw), str(count)], timeout)
                actual = response.get("stdout", "").strip()
                status = response.get("status", "AGREED")
                if status == "AGREED" and (response["returncode"] or response["stderr"]):
                    status = "ERROR"
                elif status == "AGREED" and actual != expected:
                    status = "MISMATCH"
                cases.append({
                    "operation": operation, "raw": raw, "requested": count,
                    "expected": expected, "observed": actual, "status": status,
                })
    status = next((case["status"] for case in cases if case["status"] != "AGREED"), "BOUNDED_AGREEMENT")
    return {"status": status, "executable_sha256": digest(path), "cases": cases}


def check(args):
    tools = {name: tool(name, getattr(args, name), args.timeout) for name in TOOLS}
    report = {
        "schema": SCHEMA,
        "execution_profile": "linux-x86_64; raw signed 64-bit RAX; count 0..2^63-1",
        "timeout_seconds_per_command": args.timeout,
        "artifacts_sha256": {str(path): digest(ROOT / path) for path in (BOOGIE_MODEL, LEAN_MODEL)},
        "subject_sha256": {str(path): digest(path) for path in args.subject},
        "tools": tools,
        "source_claims": {
            "decoder_body_conformance": {"status": "UNKNOWN", "open_premises": ["source/model correspondence"]},
            "public_contract_refinement": {
                "status": "UNKNOWN",
                "open_premises": [
                    "source/model correspondence", "Linux x86-64 read/write return-envelope assumption",
                ],
            },
        },
    }
    if any(info["status"] != "READY" for info in tools.values()):
        return dict(report, status="ERROR" if any(info["status"] == "ERROR" for info in tools.values()) else "UNKNOWN")
    claims = {
        name: boogie_check(tools, procedure, args.timeout)
        for name, procedure in OBLIGATIONS.items()
    }
    controls = {
        name: dict(control, **boogie_check(tools, control["procedure"], args.timeout, negative=True))
        for name, control in CONTROLS.items()
    }
    lean = lean_check(tools["lean"]["path"], args.timeout)
    report["checked_model_claims"] = {"boogie_z3": claims, "lean": lean}
    report["model_negative_controls"] = controls
    results = [*claims.values(), *controls.values(), lean]
    if args.decoder:
        replay = replay_decoder(args.decoder, args.timeout)
        report["native_correspondence"] = replay
        results.append(replay)
    if any(result["status"] in ("ERROR", "MISMATCH") for result in results):
        return dict(report, status="ERROR")
    if any(result["status"] == "UNKNOWN" for result in results):
        return dict(report, status="UNKNOWN")
    for claim in report["source_claims"].values():
        claim["status"] = "CONDITIONAL"
    return dict(report, status="MODEL_CHECKED")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in TOOLS:
        parser.add_argument(f"--{name}", default=name)
    parser.add_argument("--subject", action="append", type=Path, default=[], help="source file to identify in the report")
    parser.add_argument("--decoder", type=Path, help="native decoder example executable for bounded replay")
    parser.add_argument("--timeout", type=float, default=15)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if not 0 < args.timeout <= 60:
        parser.error("timeout must be greater than zero and at most 60 seconds")
    if any(not path.is_file() for path in args.subject):
        parser.error("each subject must be a file")
    report = check(args)
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0 if report["status"] == "MODEL_CHECKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
