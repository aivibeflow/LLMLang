"""Check exact TLC recovery against changed sources and fresh Apalache obligations."""
import argparse
from dataclasses import asdict, dataclass, replace
from hashlib import file_digest, sha256
import json
import os
from pathlib import Path
import re
from shutil import copytree, which
from subprocess import run
from tempfile import TemporaryDirectory
import zipfile

HERE = Path(__file__).resolve().parent
JAVA_FLAGS = ("-Xmx768m", "-XX:+UseParallelGC")
TLC_FLAGS = ("-workers", "1", "-fp", "0", "-seed", "811", "-checkpoint", "0")
CKPT_FILES = {"settings.chkpt", "queue.chkpt", "vars.chkpt", "Counter-0.chkpt", "dgraph_0.chkpt"}
LARGE_LIMIT = 120000


@dataclass(frozen=True)
class Model:
    limit: int = 4
    initial_outside: bool = False
    widen_step: bool = False
    weak_fairness: bool = True


def model_text(model):
    source = (HERE / "Counter.tla").read_text()
    source = source.replace("Limit == 4", f"Limit == {model.limit}")
    if model.initial_outside:
        source = source.replace("Init == x = 0", "Init == x = (Limit + 1)")
    if model.widen_step:
        source = source.replace("x < Limit", "x < (Limit + 1)")
    if not model.weak_fairness:
        source = source.replace(" /" + chr(92) + " WF_x(Next)", "")
    return source


def write_model(directory, model):
    directory.mkdir()
    (directory / "Counter.tla").write_text(model_text(model))
    (directory / "Counter.cfg").write_bytes((HERE / "Counter.cfg").read_bytes())


def fingerprint(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def manifest(directory, engine, flags):
    return {
        "engine": engine, "spec": fingerprint(directory / "Counter.tla"),
        "config": fingerprint(directory / "Counter.cfg"), "flags": [*JAVA_FLAGS, *flags],
    }


def inventory(directory):
    return {path.relative_to(directory).as_posix(): fingerprint(path)
            for path in sorted(directory.rglob("*")) if path.is_file()}


def matched(current_model, original_model, current_files, original_files):
    return current_model == original_model and current_files == original_files


def launch(args, directory):
    result = run(args, cwd=directory, env={**os.environ, "LC_ALL": "C", "TZ": "UTC"},
                 capture_output=True, text=True, timeout=45)
    return result.returncode, result.stdout + result.stderr


def tlc(tools, directory, *, start=False, recover=None):
    command = HERE / "Checkpoint.java" if start else "tlc2.TLC"
    mode = ["-recover", str(recover)] if recover else ["-metadir", "states"]
    return launch([tools.java, *JAVA_FLAGS, "-cp", tools.tlc, command,
                   *TLC_FLAGS, *mode, "-config", "Counter.cfg", "Counter.tla"], directory)


def exact_recovery(tools, directory, checkpoint, engine, expected, files):
    actual = manifest(directory, engine, TLC_FLAGS)
    if not matched(actual, expected, inventory(checkpoint), files):
        return None
    return tlc(tools, directory, recover=checkpoint)


def classify_tlc(status, output):
    if status == 0 and "Model checking completed. No error has been found." in output:
        state_counts = re.findall(r"^(\d+) states generated, (\d+) distinct states found, (\d+) states left on queue\.",
                                  output, flags=re.M)
        assert state_counts
        return {"status": "checked", "distinct": int(state_counts[-1][1])}
    if "Invariant Safe is violated" in output:
        values = re.findall(r"^x = (\d+)$", output, flags=re.M)
        assert values and status
        return {"status": "safety-violation", "value": int(values[0])}
    if "Temporal property EventuallyBound was violated" in output:
        assert status and "Stuttering" in output
        return {"status": "temporal-violation", "stuttering": True}
    raise AssertionError((status, output))


def safety_oracle(model, bound, *, induction):
    initial = range(model.limit + 1) if induction else (
        model.limit + 1 if model.initial_outside else 0,
    )
    frontier = set(initial)
    observed = set(frontier)
    for _ in range(bound):
        frontier = {state + 1 for state in frontier if state < model.limit + model.widen_step}
        observed.update(frontier)
    return "checked" if all(0 <= state <= model.limit for state in observed) else "safety-violation"


def apalache(tools, directory, model, bound, *, induction):
    init = "Safe" if induction else "Init"
    status, output = launch([tools.apalache, "--out-dir=analysis", "check", f"--length={bound}",
                             f"--init={init}", "--next=Next", "--inv=Safe", "--no-deadlock=true",
                             "Counter.tla"], directory)
    result = safety_oracle(model, bound, induction=induction)
    if result == "checked":
        assert status == 0 and "Checker reports no error up to computation length" in output, (status, output)
        trace = None
    else:
        assert status == 12 and "state invariant 0 violated" in output, (status, output)
        traces = list((directory / "analysis").rglob("violation1.itf.json"))
        assert len(traces) == 1
        witness = json.loads(traces[0].read_text())
        assert witness["vars"] == ["x"] and witness["#meta"]["varTypes"] == {"x": "Int"}
        trace = [int(state["x"]["#bigint"]) for state in witness["states"]]
        assert trace and len(trace) <= bound + 1 and trace[-1] == model.limit + 1
        assert all(right == left + 1 and left < model.limit + model.widen_step
                   for left, right in zip(trace, trace[1:]))
        if induction:
            assert 0 <= trace[0] <= model.limit
        else:
            assert trace[0] == (model.limit + 1 if model.initial_outside else 0)
    return {"status": result, "bound": bound, "initialization": init, "witness": trace,
            "spec": fingerprint(directory / "Counter.tla")}


def check(tools, scratch):
    base = Model(limit=LARGE_LIMIT)
    changed_initial = replace(base, initial_outside=True)
    origin = scratch / "origin"
    write_model(origin, base)
    status, output = tlc(tools, origin, start=True)
    assert status == 73 and "Checkpointing completed" in output, (status, output)
    checkpoints = list((origin / "states").iterdir())
    assert len(checkpoints) == 1
    files = inventory(checkpoints[0])
    assert CKPT_FILES <= files.keys()
    engine = {
        "tlc_jar": fingerprint(tools.tlc), "java_launcher": fingerprint(tools.java),
        "java_vm": fingerprint(tools.java.parent.parent / "lib/server/libjvm.so"),
    }
    pinned = manifest(origin, engine, TLC_FLAGS)
    if tools.archive:
        copytree(checkpoints[0], tools.archive)
        (tools.archive / "fixture-manifest.json").write_text(
            json.dumps({"model": pinned, "checkpoint": files}, sort_keys=True, indent=2) + "\n")

    exact = scratch / "resumed"
    write_model(exact, base)
    restored = exact / "checkpoint"
    copytree(checkpoints[0], restored)
    resume_status, resume_output = exact_recovery(tools, exact, restored, engine, pinned, files)
    recovery = re.search(r"Recovery completed\. (\d+) states examined\. (\d+) states on queue\.", resume_output)
    assert recovery and int(recovery[2]) > 0
    resumed = classify_tlc(resume_status, resume_output)

    fresh = scratch / "fresh-original"
    write_model(fresh, base)
    checked = classify_tlc(*tlc(tools, fresh))
    assert resumed == checked == {"status": "checked", "distinct": LARGE_LIMIT + 1}

    changed = scratch / "fresh-changed-initial"
    write_model(changed, changed_initial)
    assert exact_recovery(tools, changed, checkpoints[0], engine, pinned, files) is None
    fresh_changed = classify_tlc(*tlc(tools, changed))
    assert fresh_changed == {"status": "safety-violation", "value": LARGE_LIMIT + 1}
    raw = scratch / "unchecked-recovery-control"
    write_model(raw, changed_initial)
    copytree(checkpoints[0], raw / "checkpoint")
    raw_status, raw_output = tlc(tools, raw, recover=raw / "checkpoint")
    assert "Recovery completed." in raw_output and classify_tlc(raw_status, raw_output) == checked

    controls = {"changed-initial": "prior-checkpoint-refused", "changed-raw-recovery": "reported-success"}
    for label, updated_model in (("changed-bound", Model()), ("changed-fairness", replace(base, weak_fairness=False))):
        edited = scratch / label
        write_model(edited, updated_model)
        assert not matched(manifest(edited, engine, TLC_FLAGS), pinned, files, files)
        controls[label] = "prior-checkpoint-refused"
    changed_config = scratch / "changed-config"
    write_model(changed_config, base)
    (changed_config / "Counter.cfg").write_text("SPECIFICATION Spec\nINVARIANT Safe\nCHECK_DEADLOCK FALSE\n")
    assert not matched(manifest(changed_config, engine, TLC_FLAGS), pinned, files, files)
    controls["changed-config"] = "prior-checkpoint-refused"
    assert not matched({**pinned, "engine": {**engine, "tlc_jar": "other"}}, pinned, files, files)
    assert not matched({**pinned, "flags": ["-workers", "2"]}, pinned, files, files)
    assert not matched(pinned, pinned, {key: value for key, value in files.items() if key != "queue.chkpt"}, files)
    controls.update({"changed-engine": "prior-checkpoint-refused", "changed-worker-profile": "prior-checkpoint-refused",
                     "destroyed-queue-role": "prior-checkpoint-refused"})

    small = Model()
    unfair = replace(small, weak_fairness=False)
    temporal_cases = {}
    for label, source, expected in (("small-fair", small, "checked"), ("small-unfair", unfair, "temporal-violation")):
        target = scratch / label
        write_model(target, source)
        decision = classify_tlc(*tlc(tools, target))
        assert decision["status"] == expected
        temporal_cases[label] = decision

    outside = replace(small, initial_outside=True)
    widened = replace(small, widen_step=True)
    apalache_cases = {}
    for label, model, bound, induction in (
        ("base-initialization", small, 0, False), ("base-consecution", small, 1, True),
        ("base-bound-five", small, 5, False), ("unfair-safety-only", unfair, 5, False),
        ("changed-initialization", outside, 0, False), ("widened-bound-four", widened, 4, False),
        ("widened-bound-five", widened, 5, False), ("widened-consecution", widened, 1, True),
    ):
        target = scratch / label
        write_model(target, model)
        apalache_cases[label] = apalache(tools, target, model, bound, induction=induction)
    assert apalache_cases["widened-bound-five"]["witness"] == list(range(6))
    assert apalache_cases["widened-consecution"]["witness"] == [4, 5]

    return {
        "exact_tlc_request": pinned, "required_checkpoint_roles": sorted(CKPT_FILES), "native_forced_exit": status,
        "recovered_nonempty_frontier": True, "original_model": asdict(base), "exact_resume": resumed,
        "fresh_original": checked, "fresh_changed_initial": fresh_changed, "controls": controls,
        "tlc_fairness": temporal_cases, "apalache_scope": "Init/Next safety without temporal fairness",
        "apalache_cases": apalache_cases,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tlc", required=True, type=Path)
    parser.add_argument("--apalache", required=True, type=Path)
    parser.add_argument("--java", default=which("java"), type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--archive", type=Path)
    tools = parser.parse_args()
    for name in ("tlc", "apalache", "java"):
        setattr(tools, name, getattr(tools, name).resolve(strict=True))
    with zipfile.ZipFile(tools.tlc) as jar:
        properties = jar.read("META-INF/MANIFEST.MF").decode()
        assert "bc1b506bdcad80bb518bf3776a9161c34ff0fc4c" in properties
    with TemporaryDirectory() as scratch:
        scratch = Path(scratch)
        java_status, java_version = launch([tools.java, "-version"], scratch)
        apalache_status, apalache_version = launch([tools.apalache, "version"], scratch)
        assert java_status == apalache_status == 0 and apalache_version.strip() == "0.63.0"
        result = check(tools, scratch)
    tools.output.write_text(json.dumps({
        "tlc": "2026.11.19.180144 bc1b506", "java": java_version.splitlines()[0],
        "apalache": apalache_version.strip(), "apalache_jar": fingerprint(tools.apalache.parent.parent / "lib/apalache.jar"),
        **result,
    }, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
