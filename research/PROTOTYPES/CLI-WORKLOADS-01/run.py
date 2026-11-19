"""Run the RT-01 CLI acceptance cases against one set of executables."""

import argparse
import os
import signal
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import Optional


@dataclass(frozen=True)
class Case:
    identifier: str
    program: str
    argv: tuple = ()
    stdin: bytes = b""
    stdout: Optional[bytes] = b""
    stderr: Optional[bytes] = b""
    success: bool = True
    broken_stdout: bool = False


INVALID = b"invalid input\n"
OVERFLOW = b"arithmetic overflow\n"


def calculation(identifier, stdin, stdout=b"", stderr=b""):
    return Case(identifier, "calculator", stdin=stdin, stdout=stdout,
                stderr=stderr, success=not stderr)


CASES = (
    Case("T-0001-01", "hello", stdout=b"Hello, world!\n"),
    Case("T-0001-02", "hello", argv=("ignored", ""), stdout=b"Hello, world!\n"),
    Case("T-0001-03", "hello", stdout=None, stderr=None, success=False, broken_stdout=True),
    Case("T-0002-01", "echo", stdout=b"\n"),
    Case("T-0002-02", "echo", argv=("hello",), stdout=b"hello\n"),
    Case("T-0002-03", "echo", argv=("alpha", "beta", "gamma"), stdout=b"alpha beta gamma\n"),
    Case("T-0002-04", "echo", argv=("two words", "x"), stdout=b"two words x\n"),
    Case("T-0002-05", "echo", argv=("", ""), stdout=b" \n"),
    Case("T-0002-06", "echo", argv=("hello",), stdout=None, stderr=None,
         success=False, broken_stdout=True),
    calculation("T-0003-01", b"12 + 30\n", b"42\n"),
    calculation("T-0003-02", b"12 - 30\n", b"-18\n"),
    calculation("T-0003-03", b"7 * -6\n", b"-42\n"),
    calculation("T-0003-04", b"20 / 4\n", b"5\n"),
    calculation("T-0003-05", b"-7 / 2\n", b"-3\n"),
    calculation("T-0003-06", b"1 / 0\n", stderr=b"division by zero\n"),
    calculation("T-0003-07", b"9223372036854775807 + 1\n", stderr=OVERFLOW),
    calculation("T-0003-08", b"-9223372036854775808 / -1\n", stderr=OVERFLOW),
    calculation("T-0003-09", b"1 % 2\n", stderr=INVALID),
    calculation("T-0003-10", b"1 + 2 3\n", stderr=INVALID),
    calculation("T-0003-11", b"  1\t+\t2  \n", b"3\n"),
    calculation("T-0003-12", b"-9223372036854775808 + 0\n", b"-9223372036854775808\n"),
    calculation("T-0003-13", b"", stderr=INVALID),
    Case("RT-01-echo-utf8", "echo", argv=("", "λ\tβ", ""), stdout=" λ\tβ \n".encode()),
    calculation("RT-01-calc-eof", b"+0007\r/\t-2", b"-3\n"),
    calculation("RT-01-calc-upper-bound", b"9223372036854775807 + 0\n", b"9223372036854775807\n"),
    calculation("RT-01-calc-upper-range", b"9223372036854775808 + 0\n", stderr=INVALID),
    calculation("RT-01-calc-lower-range", b"-9223372036854775809 + 0\n", stderr=INVALID),
    calculation("RT-01-calc-sub-overflow", b"-9223372036854775808 - 1\n", stderr=OVERFLOW),
    calculation("RT-01-calc-mul-overflow", b"9223372036854775807 * 2\n", stderr=OVERFLOW),
    calculation("RT-01-calc-missing-operand", b"1 +\n", stderr=INVALID),
    calculation("RT-01-calc-lone-sign", b"+ + 2\n", stderr=INVALID),
    calculation("RT-01-calc-non-ascii", "١ + 2\n".encode(), stderr=INVALID),
    calculation("RT-01-calc-not-whitespace", b"1\v+ 2\n", stderr=INVALID),
    calculation("RT-01-calc-embedded-nul", b"1 + 2\x00\n", stderr=INVALID),
)

PROGRAMS = ("hello", "echo", "calculator")


def run_case(command, case):
    argv = [*command, *case.argv]
    options = dict(input=case.stdin, stderr=subprocess.PIPE, timeout=5)
    if case.broken_stdout:
        reader, writer = os.pipe()
        os.close(reader)
        try:
            return subprocess.run(argv, stdout=writer, **options)
        finally:
            os.close(writer)
    return subprocess.run(argv, stdout=subprocess.PIPE, **options)


def evaluate(commands):
    failures = 0
    for case in CASES:
        try:
            result = run_case(commands[case.program], case)
        except (OSError, subprocess.TimeoutExpired) as error:
            print(f"FAIL {case.identifier}: {error}")
            failures += 1
            continue

        expected_status = "0" if case.success else "nonzero or SIGPIPE"
        status_ok = result.returncode == 0 if case.success else (
            result.returncode > 0
            or (case.broken_stdout and result.returncode == -signal.SIGPIPE)
        )
        differences = []
        if not status_ok:
            differences.append(f"exit {result.returncode}, expected {expected_status}")
        for stream in ("stdout", "stderr"):
            expected = getattr(case, stream)
            actual = getattr(result, stream)
            if expected is not None and actual != expected:
                differences.append(f"{stream} {actual!r}, expected {expected!r}")

        if differences:
            failures += 1
            print(f"FAIL {case.identifier}: {', '.join(differences)}")
        else:
            print(f"PASS {case.identifier}")
    print(f"{len(CASES) - failures}/{len(CASES)} passed")
    return int(bool(failures))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", choices=("python", "c"))
    parser.add_argument("--cc", default="cc", help="C compiler for the host reference")
    for program in PROGRAMS:
        parser.add_argument(f"--{program}", type=Path, metavar="EXECUTABLE")
    args = parser.parse_args()
    paths = {program: getattr(args, program) for program in PROGRAMS}
    if args.reference and any(paths.values()):
        parser.error("select a host reference or supply the three executables")
    if not args.reference and not all(paths.values()):
        parser.error("supply --hello, --echo, and --calculator, or select --reference")
    if os.name != "posix":
        parser.error("the acceptance cases require POSIX pipe and exit semantics")

    root = Path(__file__).resolve().parent
    if args.reference == "python":
        return evaluate({
            program: [sys.executable, "-B", str(root / "reference.py"), program]
            for program in PROGRAMS
        })
    if args.reference == "c":
        with TemporaryDirectory(prefix="rt01-cli-") as directory:
            executable = str(Path(directory) / "reference")
            try:
                subprocess.run(
                    [args.cc, "-std=c17", "-Wall", "-Wextra", "-Werror",
                     str(root / "reference.c"), "-o", executable],
                    check=True,
                    timeout=60,
                )
            except (OSError, subprocess.SubprocessError) as error:
                parser.exit(1, f"C reference compilation failed: {error}\n")
            return evaluate({program: [executable, program] for program in PROGRAMS})
    return evaluate({program: [str(path.resolve())] for program, path in paths.items()})


if __name__ == "__main__":
    sys.exit(main())
