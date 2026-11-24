"""Measure action invalidation for exact and separately linked C call sites."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from tempfile import TemporaryDirectory
from typing import Literal

from .binding import BindingSnapshot, binding_verification_key, make_binding_snapshot
from .semantic_graph import ContentStore, Dependency, digest


@dataclass(frozen=True)
class Consumer:
    index: int
    provider: str
    body_visible: bool = False


CONSUMERS = (
    *(Consumer(i, "hot") for i in range(8)),
    *(Consumer(i, "hot", True) for i in range(8, 12)),
    *(Consumer(i, "cold") for i in range(12, 16)),
)
INPUTS = (0, 1, 2, 3)
DIMENSIONS = ("linkage", "phase", "compile_provider", "compile_caller", "link",
              "verify_projected", "verify_whole_snapshot")


def _timed_child(command: list[str]) -> tuple[subprocess.CompletedProcess, int, float, float, int]:
    """Run a child and return its own user/system CPU seconds plus captured output."""
    started_wrapper = time.perf_counter_ns()
    prelude = (
        "import resource, subprocess, sys, time\n"
        "cmd = sys.argv[1:]\n"
        "before = resource.getrusage(resource.RUSAGE_CHILDREN)\n"
        "start = time.perf_counter_ns()\n"
        "p = subprocess.run(cmd, capture_output=True)\n"
        "wall = time.perf_counter_ns() - start\n"
        "after = resource.getrusage(resource.RUSAGE_CHILDREN)\n"
        "sys.stdout.buffer.write(p.stdout)\n"
        "sys.stderr.buffer.write(p.stderr)\n"
        "sys.stderr.write('\\nLLMLANG_TIMING %d %.9f %.9f %d\\n' % "
        "(wall, after.ru_utime-before.ru_utime, after.ru_stime-before.ru_stime, p.returncode))\n"
        "sys.exit(p.returncode)\n"
    )
    proc = subprocess.run([sys.executable, "-c", prelude, *command], capture_output=True, text=False)
    stderr = proc.stderr.decode(errors="replace")
    marker = "LLMLANG_TIMING "
    line = next((item for item in stderr.splitlines() if item.startswith(marker)), None)
    if line is None:
        raise RuntimeError(f"timing wrapper did not return timing metadata: {stderr}")
    _, wall, user, system, child_status = line.split()
    clean_stderr = "\n".join(item for item in stderr.splitlines() if not item.startswith(marker))
    completed = subprocess.CompletedProcess(command, int(child_status), proc.stdout, clean_stderr.encode())
    return completed, int(wall), float(user), float(system), time.perf_counter_ns() - started_wrapper


def _provider_code(symbol: str, base: int, *, body_visible: bool = False) -> str:
    scope = "static " if body_visible else ""
    return (
        f"static int peer(int x);\n"
        f"{scope}int {symbol}(int x) {{ return x == 0 ? {base} : peer(x - 1); }}\n"
        f"static int peer(int x) {{ return x == 0 ? {base + 1} : {symbol}(x - 1); }}\n"
    )


def _caller_code(consumer: Consumer, symbol: str, base: int) -> str:
    interface = (_provider_code(symbol, base, body_visible=True) if consumer.body_visible
                 else f"extern int {symbol}(int x);\n")
    results = ", ".join(f"{symbol}({argument})" for argument in INPUTS)
    return (
        '#include <stdio.h>\n' + interface +
        f'int main(void) {{ printf("{consumer.index} %d %d %d %d\\n", {results}); return 0; }}\n'
    )


class Actions:
    def __init__(self, directory: Path, compiler: str, toolchain: str, *, record_timings: bool = False):
        directory.mkdir()
        self.directory = directory
        self.compiler = compiler
        self.toolchain = toolchain
        self.files: dict[str, tuple[Path, str]] = {}
        self.results: dict[str, tuple[int, ...]] = {}
        self.executed: Counter[str] = Counter()
        self.record_timings = record_timings
        self.action_samples: list[dict] = []
        self.lookup_ns: Counter[str] = Counter()
        self.lookup_count: Counter[str] = Counter()

    def _file(self, key, output, command, action) -> tuple[Path, str]:
        if key not in self.files:
            if self.record_timings:
                completed, elapsed, user_cpu, system_cpu, wrapper_wall = _timed_child(command)
                if completed.returncode:
                    raise subprocess.CalledProcessError(
                        completed.returncode, command, completed.stdout, completed.stderr,
                    )
            else:
                completed = subprocess.run(command, check=True, capture_output=True, text=True)
                elapsed, user_cpu, system_cpu, wrapper_wall = 0, 0.0, 0.0, 0
            self.files[key] = output, sha256(output.read_bytes()).hexdigest()
            self.executed[action] += 1
            if self.record_timings:
                self.action_samples.append({
                    "action": action,
                    "wall_ns": elapsed,
                    "wrapper_wall_ns": wrapper_wall,
                    "user_cpu_s": user_cpu,
                    "system_cpu_s": system_cpu,
                    "output_bytes": output.stat().st_size,
                    "command": command,
                })
        return self.files[key]

    def compile(self, source: str, optimization: str, action: str) -> tuple[Path, str]:
        started = time.perf_counter_ns() if self.record_timings else 0
        flags = ("-std=c17", optimization)
        key = digest(("rt11-c-compile-v1", self.toolchain, flags, source))
        input_path = self.directory / f"{key}.c"
        output = self.directory / f"{key}.o"
        if key not in self.files:
            input_path.write_text(source, encoding="utf-8")
        result = self._file(key, output, (
            self.compiler, *flags, "-c", str(input_path), "-o", str(output)
        ), action)
        if self.record_timings:
            self.lookup_ns[action] += time.perf_counter_ns() - started
            self.lookup_count[action] += 1
        return result

    def link(self, objects: tuple[tuple[Path, str], ...]) -> tuple[Path, str]:
        started = time.perf_counter_ns() if self.record_timings else 0
        key = digest(("rt11-c-link-v1", self.toolchain, [object_hash for _, object_hash in objects]))
        output = self.directory / f"{key}.bin"
        result = self._file(key, output, (
            self.compiler, *(str(path) for path, _ in objects), "-o", str(output)
        ), "link")
        if self.record_timings:
            self.lookup_ns["link"] += time.perf_counter_ns() - started
            self.lookup_count["link"] += 1
        return result

    def verify(
        self, action: str, key: str, executable: Path, label: int, allowed_bases: tuple[int, ...],
    ) -> tuple[int, ...]:
        started = time.perf_counter_ns() if self.record_timings else 0
        if key not in self.results:
            if self.record_timings:
                completed, elapsed, user_cpu, system_cpu, wrapper_wall = _timed_child([str(executable)])
                if completed.returncode:
                    raise subprocess.CalledProcessError(
                        completed.returncode, [str(executable)], completed.stdout, completed.stderr,
                    )
                fields = completed.stdout.decode().split()
            else:
                fields = subprocess.check_output([str(executable)], text=True).split()
                elapsed, user_cpu, system_cpu, wrapper_wall = 0, 0.0, 0.0, 0
            label_and_outputs = tuple(map(int, fields))
            accepted = {(label, *(base + (x % 2) for x in INPUTS)) for base in allowed_bases}
            if label_and_outputs not in accepted:
                raise ValueError(f"observations violate the bench contract: {label_and_outputs}")
            self.executed[action] += 1
            self.results[key] = label_and_outputs[1:]
            if self.record_timings:
                self.action_samples.append({
                    "action": action, "wall_ns": elapsed, "user_cpu_s": user_cpu,
                    "system_cpu_s": system_cpu, "wrapper_wall_ns": wrapper_wall,
                    "output_bytes": len(completed.stdout),
                    "command": [str(executable)],
                })
        if self.record_timings:
            self.lookup_ns[action] += time.perf_counter_ns() - started
            self.lookup_count[action] += 1
        return self.results[key]


def _binding(
    store: ContentStore,
    *,
    hot_base: int,
    tighten: bool = False,
    previous: BindingSnapshot | None = None,
) -> BindingSnapshot:
    selected = {}
    for role, base, allowed in (("hot", hot_base, [11] if tighten else [10, 11]), ("cold", 40, [40])):
        contract = store.put("contract", {"abi": "int(int)", "inputs": INPUTS, "bases": allowed})
        implementation = store.put("implementation", {"base": base}, [Dependency("implements", contract)])
        selected[role] = (contract, implementation)
    roots = () if previous is None else (previous.root_hash,)
    return make_binding_snapshot(store, selected, roots)


def _build(
    store: ContentStore,
    actions: Actions,
    binding: BindingSnapshot,
    linkage: Literal["exact", "separate"],
    optimization: str,
) -> tuple[dict[int, tuple[int, ...]], dict[int, str]]:
    actions.executed.clear()
    providers = {}
    for row in binding.bindings:
        target = binding.resolve(row.key, row.contract_hash)
        base = store.get(target).payload["base"]
        symbol = f"provider_{target}" if linkage == "exact" else f"provider_{row.key}"
        provider = actions.compile(_provider_code(symbol, base), optimization, "compile_provider")
        providers[row.key] = (row, base, symbol, provider)

    outputs, compile_inputs = {}, {}
    for consumer in CONSUMERS:
        row, base, symbol, provider = providers[consumer.provider]
        if consumer.body_visible:
            symbol = "local_provider"
        source = _caller_code(consumer, symbol, base)
        compile_inputs[consumer.index] = digest((source, optimization, actions.toolchain))
        caller = actions.compile(source, optimization, "compile_caller")
        executable, artifact = actions.link((caller,) if consumer.body_visible else (caller, provider))
        allowed = tuple(store.get(row.contract_hash).payload["bases"])
        verification = digest(("rt11-executable-verification-v1", artifact, row.contract_hash,
                               INPUTS, actions.toolchain))
        projected = digest(("rt11-selected-binding.v1", row.record()))
        projected_key = digest(("rt11-projected-verification.v1", verification, projected))
        whole_key = binding_verification_key(verification, binding.root_hash)
        outputs[consumer.index] = actions.verify(
            "verify_projected", projected_key, executable, consumer.index, allowed,
        )
        whole = actions.verify("verify_whole_snapshot", whole_key, executable, consumer.index, allowed)
        if whole != outputs[consumer.index]:
            raise AssertionError("verification policies disagree on outputs")
    return outputs, compile_inputs


def experiment(compiler: str, *, record_timings: bool = False) -> dict:
    executable = shutil.which(compiler)
    if executable is None:
        raise ValueError(f"C compiler not found: {compiler}")
    version = subprocess.check_output([executable, "--version"], text=True)
    target = subprocess.check_output([executable, "-dumpmachine"], text=True).strip()
    toolchain = digest((executable, version, target))
    store = ContentStore()
    initial = _binding(store, hot_base=10)
    implementation_edit = _binding(store, hot_base=11, previous=initial)
    contract_edit = _binding(store, hot_base=11, tighten=True, previous=implementation_edit)
    history_edit = _binding(store, hot_base=11, tighten=True, previous=contract_edit)
    phases = (
        ("cold", initial, "-O0"),
        ("warm", initial, "-O0"),
        ("implementation", implementation_edit, "-O0"),
        ("contract", contract_edit, "-O0"),
        ("history", history_edit, "-O0"),
        ("flags", history_edit, "-O2"),
    )
    measurements, witness = [], {}
    reference = {}
    with TemporaryDirectory(prefix="llmlang-rt11-") as folder:
        root = Path(folder)
        for linkage in ("exact", "separate"):
            cache = Actions(root / linkage, executable, toolchain, record_timings=record_timings)
            for phase, snapshot, flags in phases:
                sample_start = len(cache.action_samples)
                lookup_before = cache.lookup_ns.copy()
                lookup_count_before = cache.lookup_count.copy()
                result, compile_inputs = _build(store, cache, snapshot, linkage, flags)
                clean = Actions(root / f"clean-{linkage}-{phase}", executable, toolchain,
                                record_timings=record_timings)
                oracle, _ = _build(store, clean, snapshot, linkage, flags)
                if result != oracle or result != reference.setdefault(phase, oracle):
                    raise AssertionError(f"semantic output mismatch in {linkage}/{phase}")
                row = dict(zip(DIMENSIONS, (linkage, phase, *(
                    cache.executed[name] for name in DIMENSIONS[2:]
                ))))
                if record_timings:
                    row["incremental_timing"] = {
                        "subprocess_samples": cache.action_samples[sample_start:],
                        "lookup_total_ns": {name: value - lookup_before[name]
                                            for name, value in cache.lookup_ns.items()},
                        "lookup_calls": {name: value - lookup_count_before[name]
                                         for name, value in cache.lookup_count.items()},
                        "clean_oracle_samples": clean.action_samples,
                        "clean_oracle_lookup_total_ns": dict(clean.lookup_ns),
                    }
                measurements.append(row)
                if linkage == "separate" and phase in ("cold", "implementation"):
                    witness[phase] = {"compile_input": compile_inputs[0], "outputs": result[0]}
    if (witness["cold"]["compile_input"] != witness["implementation"]["compile_input"]
            or witness["cold"]["outputs"] == witness["implementation"]["outputs"]):
        raise AssertionError("the fixture must distinguish compile reuse from behavioral reuse")
    return {
        "compiler": version.splitlines()[0],
        "target": target,
        "action_counts": measurements,
        "unsafe_verification_key_witness": witness,
        "timing_scope": (
            "one process execution per cache miss; user/system CPU from child rusage; "
            "lookup_total_ns includes action key construction, cache membership, and surrounding "
            "action setup, so it is not a pure hash or lookup measurement"
            if record_timings else None
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="cc")
    parser.add_argument("--timings", action="store_true",
                        help="include per-miss wall/CPU/output samples and surrounding lookup timing")
    parser.add_argument("--repeat", type=int, default=1,
                        help="run the complete paired experiment this many times (default: 1)")
    parser.add_argument("--output", type=Path,
                        help="write JSON to a file instead of stdout")
    options = parser.parse_args()
    if options.repeat < 1:
        parser.error("--repeat must be at least 1")
    runs = [experiment(options.cc, record_timings=options.timings) for _ in range(options.repeat)]
    report = {"schema": "rt11-action-benchmark-timing-v1", "repeat": options.repeat,
              "runs": runs}
    rendered = json.dumps(report, indent=2)
    if options.output:
        options.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
