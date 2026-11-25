"""Compare closed and extensible Rust sums using independently compiled consumers."""

import argparse
from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
ACCEPT = 'Outcome::Accepted(value) => ("accepted", i32::from(value)),'
DENY = 'Outcome::Denied(value) => ("denied", i32::from(value)),'
DEFER = 'Outcome::Deferred(value) => ("deferred", i32::from(value)),'
UNSUPPORTED = '_ => ("unsupported", -1),'
ASSUME_SUCCESS = '_ => ("accepted", i32::from(input)),'
CONSUMERS = {
    "exhaustive-old": (ACCEPT, DENY),
    "explicit-unknown": (ACCEPT, DENY, UNSUPPORTED),
    "wildcard-success": (ACCEPT, DENY, ASSUME_SUCCESS),
    "exhaustive-new": (ACCEPT, DENY, DEFER),
    "new-with-explicit-unknown": (ACCEPT, DENY, DEFER, UNSUPPORTED),
}


def provider(extended, new):
    attribute = "#[non_exhaustive]\n" if extended else ""
    new_variant = "    Deferred(u8),\n" if new else ""
    third_bucket = "Deferred" if new else "Denied"
    return f"""{attribute}pub enum Outcome {{
    Accepted(u8),
    Denied(u8),
{new_variant}}}

pub fn classify(input: u8) -> Outcome {{
    match input % 3 {{
        0 => Outcome::Accepted(input),
        1 => Outcome::Denied(input),
        _ => Outcome::{third_bucket}(input),
    }}
}}
"""


def consumer(arms):
    clauses = "\n".join(f"            {arm}" for arm in arms)
    return f"""use provider::Outcome;

fn main() {{
    for input in 0_u8..=255 {{
        #[allow(unreachable_patterns)]
        let (status, payload) = match provider::classify(input) {{
{clauses}
        }};
        println!("{{input}} {{status}} {{payload}}");
    }}
}}
"""


def expected_error(name, extended, new):
    if not new and name in {"exhaustive-new", "new-with-explicit-unknown"}:
        return "E0599"
    if name == "exhaustive-old" and (extended or new):
        return "E0004"
    if extended and name == "exhaustive-new":
        return "E0004"
    return None


def oracle(name, new):
    rows = []
    for value in range(256):
        bucket = value % 3
        recorded = value
        if bucket == 0:
            status = "accepted"
        elif bucket == 1 or not new:
            status = "denied"
        elif name == "explicit-unknown":
            status, recorded = "unsupported", -1
        elif name == "wildcard-success":
            status = "accepted"
        else:
            status = "deferred"
        rows.append((value, status, recorded))
    return rows


def execute(command, directory, check=True):
    return subprocess.run(command, cwd=directory, check=check, text=True,
                          capture_output=True, timeout=60)


def compare(binary, directory, name, new):
    original = execute([str(binary)], directory).stdout
    values = [(int(value), status, int(payload)) for value, status, payload in
              (line.split() for line in original.splitlines())]
    expected = oracle(name, new)
    if values != expected:
        raise AssertionError((name, new, values, expected))
    wrongful_success = sum(new and value % 3 == 2 and status == "accepted"
                           for value, status, _ in values)
    return {"observations": len(values), "status_counts": dict(sorted(Counter(row[1] for row in values).items())),
            "unrecognized_as_success": wrongful_success, "trace_sha256": sha256(original.encode()).hexdigest()}


def verify(rustc, directory):
    recorded = {}
    for opt, extended, new in product((0, 3), (False, True), (False, True)):
        profile = f"{'open' if extended else 'closed'}-v{2 if new else 1}-O{opt}"
        build = directory / profile
        build.mkdir()
        code = build / "provider.rs"
        code.write_text(provider(extended, new), encoding="utf-8")
        archive = build / "libprovider.rlib"
        execute([rustc, "--edition=2021", "--crate-type=rlib", f"-Copt-level={opt}",
                 str(code), "-o", str(archive)], build)
        cases = {}
        for name, arms in CONSUMERS.items():
            candidate = build / "consumer.rs"
            candidate.write_text(consumer(arms), encoding="utf-8")
            binary = build / "consumer"
            result = execute([rustc, "--edition=2021", f"-Copt-level={opt}", "--extern",
                              f"provider={archive}", str(candidate), "-o", str(binary)], build, check=False)
            error_codes = set(re.findall(r"^error\[(E\d+)\]", result.stderr, re.MULTILINE))
            wanted = expected_error(name, extended, new)
            if (result.returncode == 0, error_codes) != (wanted is None, {wanted} if wanted else set()):
                raise AssertionError((profile, name, wanted, result.stderr))
            if wanted is None:
                cases[name] = {"compile": "admitted", **compare(binary, build, name, new)}
            else:
                cases[name] = {"compile": wanted}
        recorded[profile] = cases
    all_cases = [case for profile in recorded.values() for case in profile.values()]
    return {
        "rustc": execute([rustc, "-vV"], directory).stdout.splitlines(),
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "compile_cases": len(all_cases),
        "native_links": sum("observations" in case for case in all_cases),
        "native_observations": sum(case.get("observations", 0) for case in all_cases),
        "wrongful_success_in_wildcard_controls": sum(case.get("unrecognized_as_success", 0) for case in all_cases),
        "profiles": recorded,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rustc", default="rustc")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-sum-extension-") as work:
        print(json.dumps(verify(args.rustc, Path(work)), indent=2))
