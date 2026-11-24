"""Link generated COR-13 Rust callers to an independently compiled C provider."""
import argparse
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import get_args

HERE = Path(__file__).resolve().parent
PROTOTYPE = HERE.parents[2] / "PROTOTYPES" / "RT-04-01"
sys.path.insert(0, str(PROTOTYPE))

from rt04_return_disposition import Disposition, TransferTiming
from rt04_rust_owned_probe import _encode, generate
from rt04_shared_owned_handlers import PRESERVE_SOURCE, RECOVER_SOURCE, compile_caller, execute
from rt04_shared_owned_workload import Inputs


def replace_exact(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"generated COR-13 runtime changed at anchor {old!r}")
    return text.replace(old, new)


def generate_linked(source, timing, *, status_only=False):
    text = generate(source, timing)
    substitutions = (
        ("struct Handle(Roles);", "struct Handle(Roles, u32);"),
        ("        trace.release(slot, disposition);",
         "        let disposition = release(self.1, disposition);\n        trace.release(slot, disposition);"),
        ("    if !first.permits(None) {",
         "    let Some(handle_token) = acquire(0, first) else {"),
        ('        return trace;\n    }\n\n    trace.event("check", "handle", "ok");',
         '        return trace;\n    };\n\n    trace.event("check", "handle", "ok");'),
        ('    trace.event("acquire", "local", "ok");',
         '    let local = acquire(1, Roles(0, 0)).expect("scratch acquisition");\n'
         '    trace.event("acquire", "local", "ok");'),
        ("    let handle = Handle(first);", "    let handle = Handle(first, handle_token);"),
        ('    trace.release("local", local_close);',
         '    let local_close = release(local, local_close);\n    trace.release("local", local_close);'),
        ("    if second.permits(prior) {",
         '    let admitted = acquire(2, second).is_some();\n'
         '    debug_assert_eq!(admitted, second.permits(prior));\n    if admitted {'),
        ('        println!("{}", run(&line?).encode());',
         '        let row = line?;\n'
         '        let (input, mode) = row.rsplit_once(\';\').expect("physical mode");\n'
         '        unsafe { rt_begin(u32::from(mode == "1")); }\n'
         '        let trace = run(input).encode();\n'
         '        let audit = unsafe { rt_finish() };\n'
         '        println!("{trace}|{audit:010x}");'),
    )
    for old, new in substitutions:
        text = replace_exact(text, old, new)
    adapter = (HERE / "adapter.rs").read_text(encoding="utf-8")
    if status_only:
        adapter = replace_exact(adapter, "    outcome\n}",
                                "    if outcome == Disposition::Ok { outcome } else { Disposition::ConsumedError }\n}")
    return text + "\n" + adapter


def encode_input(inputs, released, physical):
    fields = (*inputs.identities, str(int(inputs.wants_value)), inputs.local_close, inputs.handle_close, released)
    return ",".join(fields) + f";{int(physical)}\n"


def encode_audit(observation, physical):
    trace = observation.trace
    live = 4 if trace.second == "started" else 0
    pending = 0
    for obligation in observation.forwarded:
        bit = {"handle": 1, "local": 2}[obligation.slot]
        if obligation.kind == "reconcile":
            pending |= bit
            if not physical:
                live |= bit
        else:
            live |= bit
    starts = sum(event[0] == "acquire" for event in trace.events)
    releases = sum(event[0] == "release" for event in trace.events)
    closes = starts - live.bit_count()
    return f"{live | pending << 8 | starts << 16 | releases << 24 | closes << 32:010x}"


def checked_run(args, *, data=None):
    return subprocess.run(args, input=data, capture_output=True, text=True, check=True, timeout=90).stdout


def digest(text):
    return sha256(text.encode()).hexdigest()


def tool_banner(tool):
    return checked_run([tool, "--version"]).splitlines()[0]


def compare(cc, rustc):
    identities = (*product("abc", repeat=4), ("a", "b", "c", "d"))
    dispositions = get_args(Disposition)
    cases = [
        (Inputs(ids, wants, local, handle), released)
        for ids, wants, local, handle, released in product(
            identities, (False, True), dispositions, dispositions, dispositions,
        )
    ]
    rows = "".join(encode_input(*case, physical) for case in cases for physical in (False, True))
    fixtures = {
        "forwarding": PRESERVE_SOURCE, "recovery": RECOVER_SOURCE,
        "retargeted": RECOVER_SOURCE.replace("destination_alias = d", "destination_alias = a"),
    }
    result = {}
    control = None
    with TemporaryDirectory(prefix="rt13-owned-abi-") as directory:
        out = Path(directory)
        target, binary = out / "caller.rs", out / "caller"
        for opt in ("0", "3"):
            # Link an independent object, keeping the fixture C ABI outside the Rust compiler.
            provider = out / f"provider-{opt}.o"
            checked_run([cc, "-std=c17", "-Wall", "-Wextra", "-Werror", f"-O{opt}",
                         "-c", str(HERE / "provider.c"), "-o", str(provider)])
            exports = subprocess.check_output(["nm", "-g", "--defined-only", str(provider)], text=True, timeout=10)
            symbols = sorted(line.split()[-1] for line in exports.splitlines())
            assert symbols == ["rt_acquire", "rt_begin", "rt_finish", "rt_release"], symbols
            for (label, source), timing in product(fixtures.items(), get_args(TransferTiming)):
                caller = compile_caller(source, timing)
                reference = [execute(caller, inputs, released) for inputs, released in cases]
                expected = []
                physical_splits = 0
                for observation in reference:
                    base = _encode(observation)
                    retained_fds = encode_audit(observation, False)
                    consumed_fds = encode_audit(observation, True)
                    expected.extend([f"{base}|{retained_fds}", f"{base}|{consumed_fds}"])
                    physical_splits += retained_fds != consumed_fds
                code = generate_linked(source, timing)
                target.write_text(code, encoding="utf-8")
                build = [rustc, "--edition=2021", "-D", "warnings", "-C", f"opt-level={opt}",
                         "-C", f"link-arg={provider}", str(target), "-o", str(binary)]
                checked_run(build)
                stdout = checked_run([str(binary)], data=rows)
                got = stdout.splitlines()
                if got != expected:
                    for index, (actual, wanted) in enumerate(zip(got, expected, strict=True)):
                        if actual != wanted:
                            raise AssertionError((label, timing, opt, cases[index // 2], index % 2, wanted, actual))
                    raise AssertionError((label, timing, opt, len(got), len(expected)))
                result[f"{label}/{timing}/O{opt}"] = {
                    "rows": len(got), "physical_split_pairs": physical_splits,
                    "second_starts_per_physical_mode": sum(o.trace.second == "started" for o in reference),
                    "generated_rust_sha256": digest(code), "trace_and_audit_sha256": digest(stdout),
                }

                if (label, timing, opt) == ("retargeted", "after_cleanup", "3"):
                    mutation = generate_linked(source, timing, status_only=True)
                    target.write_text(mutation, encoding="utf-8")
                    checked_run(build)
                    changed = checked_run([str(binary)], data=rows).splitlines()
                    differences = sum(a != b for a, b in zip(changed, expected, strict=True))
                    assert differences > 0, "status-only adapter preserved every outcome"
                    control = {"variant": f"{label}/{timing}/O{opt}", "different_rows": differences,
                               "rows": len(changed)}
    assert control is not None

    return {"format": "rt13-native-owned-abi/1", "python": sys.version.split()[0],
            "cc": tool_banner(cc), "rustc": tool_banner(rustc),
            "provider_sha256": digest((HERE / "provider.c").read_text(encoding="utf-8")),
            "adapter_sha256": digest((HERE / "adapter.rs").read_text(encoding="utf-8")),
            "provider_symbols": symbols, "runs": result, "status_only_control": control}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--rustc", default="rustc")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(compare(args.cc, args.rustc), sort_keys=True, indent=2) + "\n",
                           encoding="utf-8")
