"""Compare exact Lean CLI, Pantograph protocol and programmatic library evidence."""
import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import file_digest, sha256
import json
import os
from pathlib import Path
import select
from subprocess import PIPE, Popen, check_output, run
from tempfile import TemporaryDirectory
from time import monotonic, sleep

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PIN = "12d7ee828dc8e572007df4a6f4dc2438cd0afa18"
UPSTREAM = "d704b851542b1d2caf1287f65c49f5011f687c05"
SOURCE = ROOT / "research/formal-verification/RT-32/LEAN-ARTIFACT-REPLAY-01/Defs.lean"
EXACT = "∀ n : Nat, CacheTrial.step n = n"
STATEMENTS = (
    ("definition", EXACT, "intro n; rfl"),
    ("integer", "∀ n : Nat, n + 0 = n", "intro n; rfl"),
    ("assumption", "∀ P : Prop, P → P", "intro P h; exact h"),
    ("equality", "∀ x : Nat, x = x", "intro x; rfl"),
    ("constructor", "True ∧ True", "exact ⟨True.intro, True.intro⟩"),
    ("boolean", "Bool.not false = true", "rfl"),
)


def digest(path):
    with path.open("rb") as source:
        return file_digest(source, "sha256").hexdigest()


def exact_term(term):
    return sha256(term.encode()).hexdigest()


def environment(tools, workspace):
    return {**os.environ, "PATH": str(tools.lean.parent) + os.pathsep + os.environ["PATH"],
            "LEAN_PATH": os.pathsep.join(map(str, (workspace, tools.library))), "LC_ALL": "C"}


def prepare(tools, workspace, source):
    workspace.mkdir()
    (workspace / "Defs.lean").write_bytes(source)
    (workspace / "Delay.lean").write_bytes((HERE / "Delay.lean").read_bytes())
    for module in ("Defs", "Delay"):
        check_output([tools.lean, "-o", f"{module}.olean", f"{module}.lean"],
                     cwd=workspace, env=environment(tools, workspace))
    return tuple(digest(workspace / name) for name in ("Defs.lean", "Defs.olean", "Delay.lean", "Delay.olean"))


@dataclass(frozen=True)
class Handle:
    session: object
    generation: int
    environment: tuple[str, ...]
    claim: str
    id: int


class Protocol:
    def __init__(self, worker, environment_id):
        self.worker = worker
        self.environment_id = environment_id
        self.generation = 0

    def line(self):
        assert select.select([self.worker.stdout], [], [], 8)[0], "no Pantograph response"
        result = self.worker.stdout.readline()
        assert result
        return result

    def send(self, raw):
        self.worker.stdin.write(raw + "\n")
        self.worker.stdin.flush()
        output = json.loads(self.line())
        assert isinstance(output, dict)
        return output

    def ask(self, command, value=None):
        return self.send(json.dumps({"cmd": command, "payload": value or {}}, ensure_ascii=False))

    def create(self, claim):
        opened = self.ask("goal.start", {"expr": claim})
        assert type(opened["stateId"]) is int
        return Handle(self, self.generation, self.environment_id, exact_term(claim), opened["stateId"])

    def current(self, handle, claim):
        return (handle.session is self and handle.generation == self.generation
                and handle.environment == self.environment_id and handle.claim == exact_term(claim))

    def tactic(self, handle, claim, command):
        if not self.current(handle, claim):
            return {"error": "wrong-client-scope"}
        return self.ask("goal.tactic", {"stateId": handle.id, "tactic": command})

    def reset(self):
        reply = self.ask("reset")
        assert "nGoals" in reply
        self.generation += 1


@contextmanager
def protocol(tools, directory, environment_id):
    with Popen([tools.repl, "Defs", "Delay"], cwd=directory, env=environment(tools, directory),
               stdin=PIPE, stdout=PIPE, stderr=PIPE, text=True) as worker:
        try:
            session = Protocol(worker, environment_id)
            assert session.line().strip() == "ready."
            yield session
            _, errors = worker.communicate("\n", timeout=8)
            assert worker.returncode == 0 and not errors, errors
        finally:
            if worker.poll() is None:
                worker.kill()
                worker.wait(timeout=5)


def kernel(tools, directory, claim, evidence, *, allow_unused_binder=False):
    lint = "set_option linter.unusedVariables false in\n" if allow_unused_binder else ""
    body = f"import Defs\n{lint}theorem replay : {claim} := {evidence}\n#print axioms replay\n"
    source = directory / "Checked.lean"
    source.write_text(body)
    result = run([tools.lean, "-DwarningAsError=true", source], cwd=directory, env=environment(tools, directory),
                 capture_output=True, text=True, timeout=10)
    if result.returncode:
        return "refused"
    assert "'replay' does not depend on any axioms" in result.stdout
    return "checked"


def native(tools, directory, claim, term):
    result = check_output([tools.lean, "--run", HERE / "Native.lean", claim, term], cwd=directory,
                          env=environment(tools, directory), text=True, timeout=10).strip()
    return result


def materialize(session, response):
    assert response["goals"] == [] and not response["hasSorry"] and not response["hasUnsafe"], response
    theorem = session.ask("goal.print", {"stateId": response["nextStateId"], "rootExpr": True})
    assert not any(theorem[key] for key in ("rootHasMVar", "rootHasSorry", "rootHasUnsafe"))
    assert theorem["goals"] == []
    return theorem["root"]["pp"]


def restore(session, checkpoint, environment_id, expected_payload):
    if session.environment_id != environment_id:
        return {"error": "wrong-environment"}
    data = checkpoint.read_bytes()
    if sha256(data).hexdigest() != expected_payload:
        return {"error": "wrong-checkpoint-bytes"}
    with TemporaryDirectory() as temporary:
        copy = Path(temporary) / "verified-state"
        copy.write_bytes(data)
        return session.ask("goal.load", {"path": str(copy)})


def cancel_cli(tools, directory):
    pending = directory / "Pending.lean"
    pending.write_text("import Delay\ntheorem pendingClaim : True := by\n"
                       "  fixture_announced_pause\n  exact True.intro\n")
    with Popen([tools.lean, pending], cwd=directory, env=environment(tools, directory),
               stdout=PIPE, stderr=PIPE, text=True) as worker:
        try:
            marker = directory / "pending.signal"
            deadline = monotonic() + 6
            while not marker.exists() or marker.read_text() != "pending\n":
                assert worker.poll() is None and monotonic() < deadline
                sleep(0.01)
            worker.terminate()
            out, _ = worker.communicate(timeout=4)
            assert worker.returncode == -15 and not out.strip()
        finally:
            if worker.poll() is None:
                worker.kill()
                worker.wait(timeout=4)
    assert kernel(tools, directory, "True", "True.intro") == "checked"
    return "worker-terminated-without-proof"


def comparison(tools, directory, correct_id, alternative, alternative_id):
    results = {}
    saved = directory / "goal-state"
    with protocol(tools, directory, correct_id) as client:
        for name, claim, tactic in STATEMENTS:
            handle = client.create(claim)
            reply = client.tactic(handle, claim, tactic)
            term = materialize(client, reply)
            cli = kernel(tools, directory, claim, "by\n  " + tactic)
            native_result = native(tools, directory, claim, term)
            strict_term = kernel(tools, directory, claim, term)
            if name == "assumption":
                assert strict_term == "refused"
                checked_term = kernel(tools, directory, claim, term, allow_unused_binder=True)
            else:
                checked_term = strict_term
            assert cli == checked_term == "checked" and native_result == "elaborated", (
                name, cli, checked_term, native_result, term,
            )
            results[name] = {"cli": cli, "native": native_result, "protocol": checked_term,
                             "statement_sha256": exact_term(claim), "proof_sha256": exact_term(term)}
            if name == "definition":
                opening, proof_text = handle, term
                assert client.ask("goal.save", {"id": reply["nextStateId"], "path": str(saved)}) == {}
                assert saved.is_file() and saved.stat().st_size > 0
        malformed = client.send("{")
        assert malformed["error"] == "command"
        declared = client.ask("goal.start", {"expr": "$"})
        assert declared["error"] in {"parse", "elab"}
        false_claim = client.create("False")
        hinted = client.ask("expr.echo", {"expr": "True.intro", "type": "False"})
        assert hinted["type"]["pp"] == "True"
        wrong = client.tactic(false_claim, "False", "exact True.intro")
        assert "goals" not in wrong and wrong.get("messages")
        assert native(tools, directory, "False", "True.intro") == "type-mismatch"
        assert kernel(tools, directory, "False", "True.intro") == "refused"

        unfinished = client.create(EXACT)
        partial = client.tactic(unfinished, EXACT, "intro n")
        assert len(partial["goals"]) == 1
        unsafe = client.tactic(false_claim, "False", "sorry")
        assert unsafe["goals"] == [] and unsafe["hasSorry"]
        assert native(tools, directory, "False", "sorry") == "unchecked"
        assert kernel(tools, directory, "False", "sorry") == "refused"

        timeout_goal = client.create("True")
        assert client.ask("options.set", {"timeout": 40}) == {}
        delayed = client.tactic(timeout_goal, "True", "fixture_pause; exact True.intro")
        assert delayed == {"error": "io", "desc": "interrupt"}
        assert client.ask("options.set", {"timeout": 0}) == {}
        assert materialize(client, client.tactic(timeout_goal, "True", "exact True.intro"))
        client.reset()
        old_raw = client.ask("goal.print", {"stateId": opening.id})
        assert old_raw["error"] == "index"
        replacement = client.create("True")
        assert replacement.id == opening.id
        assert client.tactic(opening, EXACT, "rfl") == {"error": "wrong-client-scope"}
        assert client.tactic(replacement, EXACT, "rfl") == {"error": "wrong-client-scope"}

    with protocol(tools, directory, correct_id) as exact_new:
        assert exact_new.tactic(opening, EXACT, "rfl") == {"error": "wrong-client-scope"}
        archived_payload = digest(saved)
        reopened = restore(exact_new, saved, correct_id, archived_payload)
        restored = exact_new.ask("goal.print", {"stateId": reopened["id"], "rootExpr": True})
        assert restored["root"]["pp"] == proof_text
        assert kernel(tools, directory, EXACT, restored["root"]["pp"]) == "checked"
        altered = directory / "altered-state"
        altered.write_bytes(saved.read_bytes() + b"changed")
        assert restore(exact_new, altered, correct_id, archived_payload) == {"error": "wrong-checkpoint-bytes"}

    with protocol(tools, alternative, alternative_id) as drifted:
        assert restore(drifted, saved, correct_id, archived_payload) == {"error": "wrong-environment"}
        candidate = drifted.create(EXACT)
        refused = drifted.tactic(candidate, EXACT, "intro n; rfl")
        assert "goals" not in refused and refused.get("messages")
        assert kernel(tools, alternative, EXACT, proof_text) == "refused"
        assert native(tools, alternative, EXACT, proof_text) in {"refused", "type-mismatch"}
    return {
        "valid_claims": results,
        "controls": {
            "protocol-json": "refused", "bad-claim-elaboration": "refused", "wrong-term-all-routes": "refused",
            "unresolved-goal": "pending", "closed-but-sorry": "refused",
            "cooperative-timeout": "interrupt-without-proof", "fresh-after-timeout": "checked",
            "reset-reuses-raw-id": True, "old-logical-handle": "refused",
            "cross-session-raw-id": "refused", "exact-state-restart": "checked",
            "changed-import-restoration": "refused-before-load", "old-term-under-new-import": "refused-all-routes",
            "lean-cli-cancellation": cancel_cli(tools, directory),
            "unused-printed-binder": "strict-lint-refused-then-checked-with-scoped-option",
            "expression-echo-type-hint": "returned-other-type-explicit-comparison-refused",
            "changed-checkpoint-bytes": "refused-before-load",
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("lean", "repl", "library", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    tools = parser.parse_args()
    for name in ("lean", "repl", "library"):
        setattr(tools, name, getattr(tools, name).resolve(strict=True))
    base = check_output(["git", "show", f"{PIN}:{SOURCE.relative_to(ROOT).as_posix()}"], cwd=ROOT)
    assert SOURCE.read_bytes() == base
    lean_version = check_output([tools.lean, "--version"], text=True).strip()
    protocol_version = check_output([tools.repl, "--version"], text=True).strip()
    assert "68218e876d2a38b1985b8590fff244a83c321783" in lean_version and protocol_version == "0.3.17"
    with TemporaryDirectory() as work:
        correct, alternative = Path(work) / "base", Path(work) / "changed"
        base_id = prepare(tools, correct, base)
        changed_id = prepare(tools, alternative, base.replace(b"n + 0", b"n + 1"))
        assert base_id != changed_id
        results = comparison(tools, correct, base_id, alternative, changed_id)
    tools.output.write_text(json.dumps({
        "basis": PIN, "upstream": UPSTREAM, "lean": lean_version, "pantograph": protocol_version,
        "tool_hashes": {"lean": digest(tools.lean), "repl": digest(tools.repl),
                        "lean_shared": digest(tools.lean.parent.parent / "lib/lean/libleanshared.so"),
                        "native_repl": digest(tools.library / "Repl.olean"),
                        "native_api": digest(tools.library / "Pantograph/Library.olean")},
        "imports": {"original": base_id, "changed": changed_id}, **results,
    }, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
