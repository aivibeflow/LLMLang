"""Check Rust admission and exact native mutations against independent cases."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory


def compile_case(compiler, source, binary, *args):
    return subprocess.run(
        [compiler, "--edition=2021", "--color=never", "--error-format=json", *args,
         str(source), "-o", str(binary)],
        capture_output=True, check=False, text=True, timeout=30,
    )


def report_errors(result):
    assert result.returncode != 0
    entries = [json.loads(line) for line in result.stderr.splitlines()]
    return [entry["code"]["code"] for entry in entries
            if entry.get("level") == "error" and entry.get("code") is not None]


def expected_rows():
    for length in range(5):
        for first in range(6):
            for second in range(6):
                before = [10, 20, 30, 40][:length]
                if max(first, second) >= length:
                    status = "out-of-bounds"
                elif first == second:
                    status = "overlap"
                else:
                    status = "paired"
                    before[first], before[second] = 91, 92
                yield length, first, second, status, before


def check_output(output):
    counts = {}
    rows = []
    for record in output.splitlines():
        length, first, second, status, data = record.split(":")
        values = list(map(int, data.split(","))) if data else []
        counts[status] = counts.get(status, 0) + 1
        rows.append((int(length), int(first), int(second), status, values))
    assert rows == list(expected_rows())
    assert counts == {"paired": 20, "overlap": 10, "out-of-bounds": 150}
    return {"counts": counts, "observations_sha256": hashlib.sha256(output.encode()).hexdigest()}


def study(compiler):
    source = Path(__file__).with_name("fixture.rs")
    with TemporaryDirectory() as temporary:
        binary = Path(temporary) / "fixture"
        compiler_info = subprocess.check_output([compiler, "-Vv"], text=True).splitlines()
        valid = {}
        for level in (0, 2):
            built = compile_case(compiler, source, binary, "-Dwarnings", f"-Copt-level={level}")
            assert built.returncode == 0, built.stderr
            output = subprocess.check_output([binary], text=True, timeout=30)
            valid[str(level)] = check_output(output)
        assert valid["0"] == valid["2"]
        negative = {}
        for config, code in (("raw_indices", "E0499"), ("escaped_borrow", "E0597")):
            actual = report_errors(compile_case(compiler, source, binary, "--cfg", config))
            assert actual == [code], actual
            negative[config] = actual
    return {
        "python": platform.python_version(),
        "compiler": compiler_info,
        "valid": valid,
        "compiler_refusals": negative,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rustc", default="rustc")
    print(json.dumps(study(parser.parse_args().rustc), indent=2, sort_keys=True))
