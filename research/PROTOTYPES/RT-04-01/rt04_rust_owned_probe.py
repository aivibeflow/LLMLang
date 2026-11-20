"""Generate Rust for checked COR-13 callers and compare native observations."""

import argparse
from itertools import product
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from typing import get_args

from rt04_return_disposition import Disposition, TransferTiming
from rt04_shared_owned_handlers import CallerTrace, PRESERVE_SOURCE, RECOVER_SOURCE, compile_caller, execute
from rt04_shared_owned_workload import Inputs


RUST_VERSION = "1.85.1"
_RUNTIME = Path(__file__).with_name("rt04_owned_probe.rs")
_ARMS = {
    "success": ('("OkWithValue", HandleState::Usable(handle, kind))', "HandleState::Usable(handle, kind)"),
    "error_with_handle": ("(_, HandleState::Usable(handle, kind))", "HandleState::Usable(handle, kind)"),
    "error_reconcile": ("(_, HandleState::Reconcile(roles))", "HandleState::Reconcile(roles)"),
    "error_without_handle": ("(_, HandleState::Absent)", "HandleState::Absent"),
}


def generate(source: str, timing: TransferTiming) -> str:
    """Validate the fixture and lower its bindings and caller actions to Rust."""
    caller = compile_caller(source, timing)
    lines = [f"const EARLY_TRANSFER: bool = {str(caller.timing == 'before_cleanup').lower()};"]
    for name, pair in (("FIRST", caller.workload.first), ("SECOND", caller.workload.second)):
        left, right = map("abcd".index, (pair.source, pair.destination))
        lines.append(f"const {name}: [usize; 2] = [{left}, {right}];")
    lines += [
        "",
        "fn handle_result(trace: &mut Trace, tag: &str, state: HandleState, _disposition: Disposition) -> HandleState {",
        "    match (tag, state) {",
    ]
    actions = dict(caller.actions)
    for group, (pattern, forwarded) in _ARMS.items():
        action = actions[group]
        if action == "release_first":
            pattern = pattern.replace("handle, kind", "handle, _")
            forwarded = 'handle.close(trace, "caller_handle", _disposition)'
        lines += [
            f"        {pattern} => {{",
            f'            trace.event("match", "{group}", "{action}");',
            f"            {forwarded}",
            "        }",
        ]
    lines += ["    }", "}"]
    return _RUNTIME.read_text(encoding="utf-8").replace("// @CHECKED_CALLER@", "\n".join(lines))


def _encode(observation: CallerTrace) -> str:
    def join(rows):
        return ";".join(",".join(row) for row in rows)

    def obligations(values):
        return join(sorted((item.slot, item.kind) for item in values))

    trace = observation.trace
    return "|".join((
        trace.result.tag if trace.result else "",
        obligations(trace.result.obligations) if trace.result else "",
        join(trace.events),
        str(int(trace.domain_error)),
        join(trace.cleanup_errors),
        trace.second,
        join((name, pair.source, pair.destination) for name, pair in trace.reservations),
        obligations(observation.forwarded),
    ))


def compare(rustc: str) -> int:
    version = subprocess.check_output([rustc, "--version"], text=True, timeout=30).strip()
    if version.split()[:2] != ["rustc", RUST_VERSION]:
        raise ValueError(f"expected rustc {RUST_VERSION}, got {version}")
    print(version, flush=True)
    dispositions = get_args(Disposition)
    # Keep Scenario 132's corpus and cover the remaining alias partition.
    identities = (*product("abc", repeat=4), ("a", "b", "c", "d"))
    cases = [
        (Inputs(ids, wants, local, handle), released)
        for ids, wants, local, handle, released in product(
            identities, (False, True), dispositions, dispositions, dispositions,
        )
    ]
    rows = "".join(
        ",".join((*inputs.identities, str(int(inputs.wants_value)), inputs.local_close, inputs.handle_close, released)) + "\n"
        for inputs, released in cases
    )
    fixtures = (
        ("forwarding", PRESERVE_SOURCE),
        ("recovery", RECOVER_SOURCE),
        ("retargeted recovery", RECOVER_SOURCE.replace("destination_alias = d", "destination_alias = a")),
    )

    checked = 0
    with TemporaryDirectory(prefix="rt04-owned-rust-") as temporary:
        target = Path(temporary) / "owned_probe.rs"
        executable = target.with_suffix("")
        for (name, source), timing in product(fixtures, get_args(TransferTiming)):
            caller = compile_caller(source, timing)
            reference = [execute(caller, inputs, released) for inputs, released in cases]
            expected = [_encode(result) for result in reference]
            starts = sum(result.trace.second == "started" for result in reference)
            target.write_text(generate(source, timing), encoding="utf-8")
            for opt in ("0", "3"):
                subprocess.run(
                    [rustc, "--edition=2021", "-D", "warnings", "-C", f"opt-level={opt}",
                     str(target), "-o", str(executable)],
                    check=True, timeout=60,
                )
                observed = subprocess.run([str(executable)], input=rows, capture_output=True,
                                          text=True, check=True, timeout=60).stdout.splitlines()
                if len(observed) != len(expected):
                    raise AssertionError(f"{name}, {timing}, opt {opt} returned {len(observed)} of {len(expected)} rows")
                for case, wanted, actual in zip(cases, expected, observed, strict=True):
                    if wanted != actual:
                        raise AssertionError(
                            f"{name}, {timing}, opt {opt}, {case}\nreference {wanted}\nnative    {actual}"
                        )
                checked += len(observed)
                print(f"{name:20} {timing:15} opt {opt}  {len(observed):5} traces  {starts:4} starts", flush=True)
    return checked


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rustc", default="rustc", help=f"path to rustc {RUST_VERSION}")
    count = compare(parser.parse_args().rustc)
    print(f"{count} native observations match the reference")
