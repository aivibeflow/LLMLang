"""Run the existing RT-01 corpus against reference and compiled MVP executables."""

import argparse
from pathlib import Path
import runpy
import subprocess
import sys
from tempfile import TemporaryDirectory

from .__main__ import WORKLOADS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boogie", default="boogie")
    parser.add_argument("--z3", default="z3")
    parser.add_argument("--rustc", default="rustc")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    runner = root / "research/language-design/PROTOTYPES/CLI-WORKLOADS-01/run.py"
    evaluate = runpy.run_path(str(runner))["evaluate"]
    cli = [sys.executable, "-B", "-m", "tools.llmlang_mvp"]
    print("Reference interpreter", flush=True)
    reference_status = evaluate({
        name: [*cli, "run", "--workload", name, "--"] for name in WORKLOADS
    })
    print("Verified native builds", flush=True)
    with TemporaryDirectory(prefix="llmlang-mvp-conformance-") as directory:
        commands = {}
        for workload in WORKLOADS:
            output = str(Path(directory) / workload)
            subprocess.run(
                [
                    *cli, "--boogie", args.boogie, "--z3", args.z3,
                    "build", "--rustc", args.rustc, "--workload", workload, "-o", output,
                ],
                check=True,
                timeout=300,
            )
            commands[workload] = [output]
        native_status = evaluate(commands)
    return int(bool(reference_status or native_status))


if __name__ == "__main__":
    sys.exit(main())
