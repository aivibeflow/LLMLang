"""Verify exact CIP publication recovery in fresh Git processes and clones."""
import argparse
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
COORDINATOR = HERE.parent / "CIP-COORDINATOR-01" / "run.py"
spec = spec_from_file_location("fixture_cip_gate", COORDINATOR)
cip = module_from_spec(spec)
sys.modules[spec.name] = cip
spec.loader.exec_module(cip)
GIT, HEAD = cip.GIT, cip.HEAD
NATIVE = cip.native
LOOKUP = NATIVE.native.lookup


def receipt_ref(operation):
    key = sha256(operation.encode()).hexdigest()
    return f"refs/llmlang/research/all/cip-receipts/{key}"


def binding(operation, approval):
    return {
        "operation": operation, "base": approval.common_base, "previous": approval.baseline_commit,
        "other_parent": approval.source_commit, "tree": approval.candidate_tree,
        "snapshot": approval.plan.candidate_root, "plan": approval.plan.plan_id,
    }


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def publish(repo, operation, approval, phase):
    ref = receipt_ref(operation)
    expected = binding(operation, approval)
    recovered = LOOKUP(repo, ref)
    if recovered is not None:
        actual = GIT(repo, "show", "-s", "--format=%B", recovered)
        if actual != canonical(expected):
            return "operation-conflict", None
        if (GIT(repo, "rev-parse", f"{recovered}^{{tree}}"),
                NATIVE.exact_parents(repo, recovered)) != (
                    expected["tree"], (expected["previous"], expected["other_parent"]),
                ):
            return "receipt-subject-mismatch", None
        return "replayed", recovered

    def synchronize(checked_repo, authorized, semantic_diff):
        assert semantic_diff.valid
        parent = authorized.baseline_commit
        candidate = NATIVE.object_commit(
            checked_repo, authorized.candidate_tree, canonical(expected),
            (parent, authorized.source_commit),
        )
        if phase == "before":
            os._exit(80)
        if phase == "race":
            print("candidate-ready", flush=True)
            if sys.stdin.readline().strip() != "resume":
                raise RuntimeError("expected fixture synchronization")
        transaction = GIT(checked_repo, "update-ref", "--stdin", check=False, payload=(
            f"start\nupdate {HEAD} {candidate} {parent}\n"
            f"create {ref} {candidate}\nprepare\ncommit\n"
        ))
        if transaction.returncode:
            return "ref-transaction-refused", None
        if phase == "after":
            os._exit(81)
        if phase == "timeout":
            print("refs-synchronized", flush=True)
            signal.pause()
        return "published", candidate

    return cip.gate(repo, approval, approval.candidate_tree, publisher=synchronize)


def worker_args(repo, operation, record, phase):
    base, start, incoming, tree = record
    return [sys.executable, "-B", str(Path(__file__).resolve()), "--worker", str(repo),
            operation, base, start, incoming, tree, phase]


def worker(args):
    repo, operation, base, start, incoming, tree, phase = args
    path = Path(repo)
    approved = cip.make_plan(path, start, base, incoming, tree)
    print(json.dumps(publish(path, operation, approved, phase)), flush=True)


def receive(process, marker):
    ready, _, _ = select.select([process.stdout], [], [], 10)
    if not ready or process.stdout.readline().strip() != marker:
        raise TimeoutError(f"worker failed to reach {marker}")


def spawn(repo, action, record, phase, expected_exit=0):
    result = subprocess.run(worker_args(repo, action, record, phase), text=True, capture_output=True,
                            timeout=15)
    assert result.returncode == expected_exit, result.stderr
    return json.loads(result.stdout) if expected_exit == 0 else None


def advance(repo):
    current = LOOKUP(repo, HEAD)
    tree = GIT(repo, "rev-parse", f"{current}^{{tree}}")
    later = NATIVE.object_commit(repo, tree, "independent ref advancement", (current,))
    GIT(repo, "update-ref", HEAD, later, current)
    return later


def clone_without_store(root, repo, label, commit, record):
    checkout = root / f"clone-{label}"
    GIT(root, "clone", "--quiet", "--no-local", "--branch", "research/all", str(repo), str(checkout))
    first = record[-1]
    assert GIT(checkout, "rev-parse", f"{commit}^{{tree}}") == first
    assert NATIVE.exact_parents(checkout, commit) == (record[1], record[2])
    catalog = cip.read_inventory(checkout, commit)
    store, reconstructed = cip.import_closed(catalog)
    local_approval = cip.make_plan(checkout, record[1], record[0], record[2], first)
    assert reconstructed.root_hash == local_approval.plan.candidate_root
    assert store.get(reconstructed.mapping["independent"]).payload["content"] == {"value": 9}
    return {"tree": catalog.tree, "snapshot": reconstructed.root_hash, "plan": local_approval.plan.plan_id}


def crash_case(root, phase):
    repo = root / phase
    base, start, first, revised = cip.prepare(repo)
    record = (base, start, *first)
    next_plan = (base, start, *revised)
    ref = receipt_ref(phase)
    if phase == "timeout":
        with subprocess.Popen(worker_args(repo, phase, record, phase), text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
            try:
                receive(process, "refs-synchronized")
                try:
                    process.wait(timeout=0.1)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    process.wait(timeout=10)
                else:
                    raise AssertionError("fixture worker returned before the induced timeout")
            finally:
                if process.poll() is None:
                    process.kill()
    else:
        spawn(repo, phase, record, phase, expected_exit=80 if phase == "before" else 81)
    if phase == "before":
        assert LOOKUP(repo, HEAD) == start and LOOKUP(repo, ref) is None
        status, accepted = spawn(repo, phase, record, "normal")
        assert status == "published"
    else:
        accepted = LOOKUP(repo, ref)
        assert accepted is not None and LOOKUP(repo, HEAD) == accepted
    assert LOOKUP(repo, ref) == accepted
    later = advance(repo)
    assert spawn(repo, phase, record, "normal") == ["replayed", accepted]
    assert spawn(repo, phase, next_plan, "normal") == ["operation-conflict", None]
    assert LOOKUP(repo, HEAD) == later
    return {"accepted_commit": accepted, "head_after_advance": later, "exact_retry": "replayed",
            "changed_payload_retry": "operation-conflict",
            "clone": clone_without_store(root, repo, phase, accepted, record)}


def race_case(root):
    repo = root / "race"
    base, start, first, _ = cip.prepare(repo)
    record = (base, start, *first)
    with subprocess.Popen(worker_args(repo, "race", record, "race"), text=True,
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        try:
            receive(process, "candidate-ready")
            later = advance(repo)
            stdout, stderr = process.communicate(input="resume\n", timeout=15)
            assert process.returncode == 0, stderr
        finally:
            if process.poll() is None:
                process.kill()
    assert json.loads(stdout) == ["ref-transaction-refused", None]
    assert LOOKUP(repo, receipt_ref("race")) is None and LOOKUP(repo, HEAD) == later
    assert spawn(repo, "race", record, "normal") == ["stale-head", None]
    return {"cas": "ref-transaction-refused", "receipt": "absent", "retry": "stale-head"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path)
    parser.add_argument("--worker", nargs=7)
    args = parser.parse_args()
    if args.worker is not None:
        worker(args.worker)
    elif args.output is not None:
        with TemporaryDirectory(prefix="llmlang-cip-recovery-") as directory:
            root = Path(directory)
            cases = {phase: crash_case(root, phase) for phase in ("before", "after", "timeout")}
            cases["race"] = race_case(root)
            version = GIT(root, "--version")
        args.output.write_text(json.dumps({"git": version, "cases": cases}, indent=2) + "\n")
    else:
        parser.error("output is required outside worker mode")


if __name__ == "__main__":
    main()
