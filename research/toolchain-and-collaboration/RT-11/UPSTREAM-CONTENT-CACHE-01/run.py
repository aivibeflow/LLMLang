#!/usr/bin/env python3
"""Compare a bounded whole-project executable cache with the native build systems."""

import argparse
import json
from pathlib import Path
import random
from tempfile import TemporaryDirectory
from time import perf_counter_ns
import sys

HERE = Path(__file__).resolve().parent
BASELINES = HERE.parent / "UPSTREAM-BUILD-BASELINES-01"
sys.path.insert(0, str(BASELINES))
import run as baseline

METHODS = ("clean", "incremental", "content")
STAGES = (("cold", 0), ("warm", 0), ("edited", 1), ("reverted", 0))


def context_digest(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return baseline.digest(payload)


def source_key(source, project_context):
    files = {path.relative_to(source).as_posix(): baseline.digest(path.read_bytes())
             for path in source.rglob("*") if path.is_file()}
    return context_digest([project_context, files]), len(files)


def prepare(name, source, target, args, environment, go_seed):
    setup = perf_counter_ns()
    command, binary, build_env = baseline.recipe(name, source, target, args, environment, go_seed)
    return command, binary, build_env, perf_counter_ns() - setup


def run_trial(name, source, trial, args, environment, go_seed, order_rng, context):
    edit_path, old, changed, probe = baseline.prepare_probe(name, source)
    original = edit_path.read_bytes()
    if original.count(old) != 1:
        raise AssertionError("The source edit no longer identifies one exact probe site")
    variant = original.replace(old, changed)
    records = {}
    mem_cache = {}
    restored = trial / "restored"
    for stage, edit in STAGES:
        if stage in ("edited", "reverted"):
            edit_path.write_bytes(variant if edit else original)
        order = list(METHODS)
        order_rng.shuffle(order)
        samples = {}
        for method in order:
            setup_ns = 0
            key = None
            files = None
            hit = None
            start = perf_counter_ns()
            if method == "content":
                key, files = source_key(source, context)
                stored = mem_cache.get(key)
                hit = stored is not None
                if hit:
                    digest, payload = stored
                    if baseline.digest(payload) != digest:
                        raise AssertionError("Cached executable digest no longer matches")
                else:
                    command, binary, build_env, setup_ns = prepare(
                        name, source, trial / f"content-{stage}", args, environment, go_seed,
                    )
                    baseline.run_command(command, source, build_env)
                    payload = binary.read_bytes()
                    mem_cache[key] = baseline.digest(payload), payload
                restored.write_bytes(payload)
                restored.chmod(0o755)
                binary = restored
                build_env = environment
            else:
                build = trial / (f"clean-{stage}" if method == "clean" else "incremental")
                command, binary, build_env, setup_ns = prepare(name, source, build, args, environment, go_seed)
                baseline.run_command(command, source, build_env)
            elapsed = perf_counter_ns() - start
            value = int(baseline.run_command([binary], source, build_env))
            if value != probe + edit or not 0 <= setup_ns <= elapsed:
                raise AssertionError((name, stage, method, value, probe, edit))
            samples[method] = {
                "wall_ns": elapsed, "preparation_ns": setup_ns, "value": value,
                "binary_sha256": baseline.digest(binary.read_bytes()), "binary_bytes": binary.stat().st_size,
                "cache_key": key, "source_files_in_key": files, "cache_hit": hit,
            }
        if len({sample["binary_sha256"] for sample in samples.values()}) != 1:
            raise AssertionError((name, stage, "Exact binary mismatch", samples))
        records[stage] = {"method_order": order, "measurements": samples}

    content = [records[stage]["measurements"]["content"] for stage, _ in STAGES]
    if [row["cache_hit"] for row in content] != [False, True, False, True]:
        raise AssertionError((name, content))
    original_key, _, edited_key, reverted_key = [row["cache_key"] for row in content]
    if original_key != reverted_key or edited_key == original_key:
        raise AssertionError((original_key, edited_key, reverted_key))
    return records


def measure(args):
    shuffle = random.Random(args.seed)
    with TemporaryDirectory(prefix="llmlang-upstream-cache-") as temp:
        root = Path(temp)
        environment = baseline.prepared_environment(root)
        archives = {name: args.sources / f"{name}.tar.gz" for name in baseline.PROJECTS}
        tools = baseline.machine(root, args, environment)
        go_source = baseline.extract(archives["pflag"], root / "go-prepare", "pflag")
        baseline.prepare_probe("pflag", go_source)
        go_seed = root / "go-seed"
        standard = baseline.standard_go_cache(args, go_source, go_seed, environment)
        output = {}
        for name, (revision, archive_hash) in baseline.PROJECTS.items():
            state = {
                "upstream_archive_sha256": archive_hash,
                "runner_sha256": baseline.digest(Path(__file__).read_bytes()),
                "shared_recipe_sha256": baseline.digest((BASELINES / "run.py").read_bytes()),
                "toolchain": tools["toolchain"],
                "fixed_environment": {key: environment[key] for key in (
                    "LC_ALL", "SOURCE_DATE_EPOCH", "CARGO_BUILD_JOBS", "CARGO_INCREMENTAL",
                    "CARGO_NET_OFFLINE", "GOENV", "GOTOOLCHAIN", "GOPROXY", "GOSUMDB",
                    "CGO_ENABLED", "GOFLAGS", "GOMAXPROCS",
                )},
            }
            trials = []
            for trial in range(args.trials):
                folder = root / f"{name}-{trial}"
                source = baseline.extract(archives[name], folder, name)
                trials.append(run_trial(name, source, folder, args, environment, go_seed, shuffle, state))
            output[name] = {"revision": revision, "key_context": state, "trials": trials}
            print(f"Checked {name} with {args.trials} trials", file=sys.stderr, flush=True)
        return {
            "schema": "llmlang-upstream-content-cache/1", "seed": args.seed, "trials": args.trials,
            "toolchain_and_host": tools, "go_precompiled_standard_packages": standard, "projects": output,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("sources", "cargo-home", "cargo", "go", "cmake"):
        parser.add_argument(f"--{argument}", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=318)
    parser.add_argument("--trials", type=int, default=3)
    args = parser.parse_args()
    if args.trials < 1:
        parser.error("provide at least one trial")
    print(json.dumps(measure(args), indent=2))
