#!/usr/bin/env python3
"""Build and execute the Linux syscall package examples on Linux x86-64."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
import sys
import tempfile


EXAMPLES = Path(__file__).resolve().parent
ROOT = EXAMPLES.parents[2]
PROGRAMS = ("echo", "copy", "pipe_poll", "child", "tcp_echo")
TCP_PAYLOAD = b"LLMLang TCP echo\x00\xff\n"
FILE_LIMIT = 4096


def digest(data):
    return hashlib.sha256(data).hexdigest()


def bounded_file_size():
    # Linux writes through the limit on the first call, then returns EFBIG.
    signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
    resource.setrlimit(resource.RLIMIT_FSIZE, (FILE_LIMIT, FILE_LIMIT))


def program_build(source, executable):
    return [
        sys.executable, "-B", str(EXAMPLES.parent / "package.py"), "build",
        str(source), "-o", str(executable),
    ]


def execute(executable, cwd, argv=(), data=b"", **kwargs):
    with subprocess.Popen(
        [str(executable), *argv], cwd=cwd, stdin=subprocess.PIPE,
        stderr=subprocess.PIPE, stdout=kwargs.pop("stdout", subprocess.PIPE),
        **kwargs,
    ) as process:
        try:
            stdout, stderr = process.communicate(data, timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            raise RuntimeError(f"example {executable.name} timed out: {stderr!r}") from None
        return {
            "argv": list(argv),
            "stdin_hex": data.hex(),
            "stdout_hex": stdout.hex() if stdout is not None else None,
            "stderr_hex": stderr.hex(),
            "exit_status": process.returncode,
        }


def validate(cases, name, observation, *, status, stdout=b"", errno=None, file=None):
    observed_file, expected_file = file if file is not None else (None, None)
    expected = {
        "exit_status": status,
        "stdout_hex": None if stdout is None else stdout.hex(),
        "kernel_errno": errno,
    }
    if file is not None:
        observation["file_hex"] = None if observed_file is None else observed_file.hex()
        expected["file_hex"] = expected_file.hex()
    stderr = bytes.fromhex(observation["stderr_hex"])
    diagnostic_matches = not stderr if errno is None else f"Kernel(Errno({errno}))".encode() in stderr
    matches = (
        observation["exit_status"] == status
        and observation["stdout_hex"] == expected["stdout_hex"]
        and diagnostic_matches
        and observed_file == expected_file
    )
    cases.append({"case": name, "observed": observation, "expected": expected, "pass": matches})


def file_bytes(path):
    return path.read_bytes() if path.is_file() else None


def run_cases(executables, directory):
    cases = []
    large_input = bytes(range(256)) * 67 + b"tail\x00"

    echo = executables["echo"]
    validate(cases, "echo-empty", execute(echo, directory), status=0)
    validate(cases, "echo-binary-multi-buffer", execute(echo, directory, data=large_input),
             status=0, stdout=large_input)
    read_end, write_end = os.pipe()
    os.close(read_end)
    try:
        broken_pipe = execute(echo, directory, data=b"not delivered", stdout=write_end)
    finally:
        os.close(write_end)
    validate(cases, "echo-broken-output", broken_pipe, status=1, stdout=None, errno=32)

    copy = executables["copy"]
    (directory / "source").write_bytes(large_input)
    copied = execute(copy, directory, ("source", "destination"))
    copied["source_file_hex"] = large_input.hex()
    validate(cases, "copy-binary-multi-buffer", copied, status=0,
             file=(file_bytes(directory / "destination"), large_input))

    duplicate = execute(copy, directory, ("source", "destination"))
    duplicate["source_file_hex"] = large_input.hex()
    validate(cases, "copy-existing-destination", duplicate, status=1, errno=17,
             file=(file_bytes(directory / "destination"), large_input))
    missing = execute(copy, directory, ("source", "missing/destination"))
    missing["source_file_hex"] = large_input.hex()
    validate(cases, "copy-destination-open-failure", missing, status=1, errno=2)

    single_buffer = large_input[:10000]
    (directory / "source").write_bytes(single_buffer)
    limited = execute(copy, directory, ("source", "limited"), preexec_fn=bounded_file_size)
    limited["rlimit_fsize_bytes"] = FILE_LIMIT
    limited["source_file_hex"] = single_buffer.hex()
    validate(cases, "copy-short-write-then-error", limited, status=1, errno=27,
             file=(file_bytes(directory / "limited"), single_buffer[:FILE_LIMIT]))

    (directory / "source").write_bytes(b"")
    empty = execute(copy, directory, ("source", "empty"))
    empty["source_file_hex"] = ""
    validate(cases, "copy-empty", empty, status=0, file=(file_bytes(directory / "empty"), b""))

    validate(cases, "pipe-timeout-and-readiness", execute(executables["pipe_poll"], directory), status=0)
    validate(cases, "child-exit-status", execute(executables["child"], directory), status=23)
    validate(cases, "local-tcp-binary-echo", execute(executables["tcp_echo"], directory),
             status=0, stdout=TCP_PAYLOAD)
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, help="write the byte-exact JSON report")
    options = parser.parse_args()

    if platform.system() != "Linux" or platform.machine() != "x86_64":
        parser.error("the example suite requires Linux x86-64")

    report = {
        "schema": "llmlang/linux.syscalls/examples/1",
        "target": "x86_64-unknown-linux-gnu",
        "running_kernel": platform.release(),
        "python": platform.python_version(),
        "rustc": subprocess.check_output(["rustc", "--version"], text=True).strip(),
        "programs": {},
    }
    with tempfile.TemporaryDirectory(prefix="llmlang-syscalls-examples-") as directory_name:
        directory = Path(directory_name)
        executables = {}
        for name in PROGRAMS:
            source = EXAMPLES / f"{name}.llmlang"
            executable = directory / name
            subprocess.run(program_build(source, executable), cwd=ROOT, check=True)
            executables[name] = executable
            report["programs"][name] = {
                "source": source.relative_to(ROOT).as_posix(),
                "source_sha256": digest(source.read_bytes()),
                "executable_sha256": digest(executable.read_bytes()),
            }
        report["cases"] = run_cases(executables, directory)

    if options.report:
        options.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failures = [case["case"] for case in report["cases"] if not case["pass"]]
    if failures:
        sys.exit("Failed example cases: " + ", ".join(failures))
    print(f"Passed {len(report['cases'])} cases across {len(PROGRAMS)} Linux syscall examples.")


if __name__ == "__main__":
    main()
