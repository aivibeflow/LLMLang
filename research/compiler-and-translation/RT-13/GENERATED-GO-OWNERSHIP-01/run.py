"""Generate Go from COR-13's checked callers and compare their exact reference traces."""

import argparse
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import get_args


HERE = Path(__file__).resolve().parent
PROTOTYPE = HERE.parents[2] / "PROTOTYPES" / "RT-04-01"
sys.path.insert(0, str(PROTOTYPE))
from rt04_return_disposition import Disposition, TransferTiming
from rt04_rust_owned_probe import _encode
from rt04_shared_owned_handlers import PRESERVE_SOURCE, RECOVER_SOURCE, compile_caller, execute
from rt04_shared_owned_workload import Inputs


FIXTURES = {
    "forwarding": PRESERVE_SOURCE,
    "recovery": RECOVER_SOURCE,
    "retargeted_recovery": RECOVER_SOURCE.replace("destination_alias = d", "destination_alias = a"),
}
PROFILES = {"default": (), "no_optimization": ("-gcflags=-N -l",)}


def digest(value):
    return sha256(value.encode("utf-8")).hexdigest()


def render(source, timing):
    caller = compile_caller(source, timing)
    lines = [f"const earlyTransfer = {str(timing == 'before_cleanup').lower()}"]
    for name, pair in (("first", caller.workload.first), ("second", caller.workload.second)):
        lines.append(f"const {name}Source = {'abcd'.index(pair.source)}")
        lines.append(f"const {name}Destination = {'abcd'.index(pair.destination)}")
    lines.extend(("", "func checkedAction(group string) string {", "    switch group {"))
    for group, action in sorted(caller.actions):
        lines.extend((f"    case {json.dumps(group)}:", f"        return {json.dumps(action)}"))
    lines.extend(("    default:", '        panic("unsupported result group")', "    }", "}"))
    return (HERE / "runtime.go.in").read_text(encoding="utf-8").replace("// @CHECKED_CALLER@", "\n".join(lines))


def call(go, args, env):
    return subprocess.run([go, *args], env=env, text=True, capture_output=True, check=True, timeout=150).stdout


def compile_run(go, directory, env, source, profile, rows):
    target = directory / "owned.go"
    target.write_text(source, encoding="utf-8")
    binary = directory / "owned"
    call(go, ["build", "-trimpath", "-buildvcs=false", "-ldflags=-buildid=", *profile, "-o", str(binary), str(target)], env)
    output = subprocess.run([str(binary)], input=rows, text=True, capture_output=True, check=True, timeout=35)
    return output.stdout.splitlines(), sha256(binary.read_bytes()).hexdigest()


def verify(go, directory, cache):
    env = {**os.environ, "CGO_ENABLED": "0", "GOOS": "linux", "GOARCH": "amd64",
           "GOAMD64": "v1", "GOCACHE": str(cache), "GOTOOLCHAIN": "local",
           "GOPROXY": "off", "GOSUMDB": "off", "GOFLAGS": "", "GOENV": "off"}
    version = call(go, ["version"], env).strip()
    if version != "go version go1.27.4 linux/amd64":
        raise ValueError(version)
    dispositions = get_args(Disposition)
    identities = (*product("abc", repeat=4), ("a", "b", "c", "d"))
    cases = [(Inputs(ids, wants, local, handle), close)
             for ids, wants, local, handle, close in product(
                 identities, (False, True), dispositions, dispositions, dispositions)]
    rows = "".join(",".join((*row.identities, str(int(row.wants_value)), row.local_close,
                            row.handle_close, close)) + "\n" for row, close in cases)
    results = {}
    for (name, source), timing in product(FIXTURES.items(), get_args(TransferTiming)):
        caller = compile_caller(source, timing)
        references = [execute(caller, inputs, close) for inputs, close in cases]
        expected = list(map(_encode, references))
        go_source = render(source, timing)
        binaries = {}
        for profile, options in PROFILES.items():
            observed, binary_sha = compile_run(go, directory, env, go_source, options, rows)
            if len(observed) != len(expected):
                raise AssertionError((name, timing, profile, len(expected), len(observed)))
            for case, wanted, actual in zip(cases, expected, observed, strict=True):
                if wanted != actual:
                    raise AssertionError((name, timing, profile, case, wanted, actual))
            binaries[profile] = binary_sha
        results[f"{name}/{timing}"] = {
            "source_sha256": digest(source), "go_sha256": digest(go_source),
            "observations_per_profile": len(expected), "binary_sha256": binaries,
            "reference_trace_sha256": digest("\n".join(expected)),
            "proposals_started": sum(observation.trace.second == "started" for observation in references),
        }

    source = FIXTURES["recovery"]
    timing = "before_cleanup"
    generated = render(source, timing)
    witnesses = {}
    for name, old, new in (
        ("drop_caller_recovery", 'return "release_first"', 'return "preserve"'),
        ("forget_alias_roles", "if second.admitted(held) {", "if second.admitted(nil) {"),
        ("force_staged_transfer", "const earlyTransfer = true", "const earlyTransfer = false"),
    ):
        changed = generated.replace(old, new, 1)
        if changed == generated:
            raise AssertionError(f"Unapplied control {name}")
        # Use the variable even in the deliberate alias mutant to satisfy Go's local usage rules.
        changed = changed.replace("if second.admitted(nil) {", "_ = held\n\tif second.admitted(nil) {")
        observed, _ = compile_run(go, directory, env, changed, (), rows)
        caller = compile_caller(source, timing)
        witnesses[name] = next(
            {"input": rows.splitlines()[index], "expected": desired, "observed": actual}
            for index, ((inputs, close), actual) in enumerate(zip(cases, observed, strict=True))
            if (desired := _encode(execute(caller, inputs, close))) != actual
        )

    rejected = []
    for label, source in (
        ("release_reconciliation_only", FIXTURES["recovery"].replace(
            'case "error_reconcile":\n        preserve()', 'case "error_reconcile":\n        release_first()')),
        ("modified_callee", FIXTURES["recovery"].replace("return move(handle)", "return error()")),
    ):
        try:
            render(source, timing)
        except ValueError:
            rejected.append(label)
        else:
            raise AssertionError(f"Unsupported source accepted: {label}")
    return {"format": "rt13-go-owned-outcomes/1", "go": version, "python": sys.version.split()[0],
            "input_rows_sha256": digest(rows), "profiles": list(PROFILES), "cases": results,
            "source_rejections": rejected, "wrong_output_controls": witnesses}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--go", default="go")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    options.cache.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="llmlang-go-owned-") as scratch:
        result = verify(options.go, Path(scratch), options.cache.resolve())
    options.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
