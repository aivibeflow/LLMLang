"""Reconcile a local Git fork candidate with an exact artifact registry handoff."""

from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
REF = "refs/heads/research/all"
ARTIFACT = b"approved fixture package bytes"
ARTIFACT_HASH = sha256(ARTIFACT).hexdigest()
OLD_ARTIFACT = sha256(b"retired fixture bytes").hexdigest()
ENV = {**os.environ, "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
       "GIT_AUTHOR_NAME": "Research Fixture", "GIT_COMMITTER_NAME": "Research Fixture",
       "GIT_AUTHOR_EMAIL": "fixture@example.invalid", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
       "GIT_AUTHOR_DATE": "2020-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2020-01-01T00:00:00Z"}


def git(repo, *args, check=True):
    return subprocess.run(["git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
                          cwd=repo, env=ENV, capture_output=True, check=check, text=True, timeout=20)


def output(repo, *args):
    return git(repo, *args).stdout.strip()


def current(repo):
    return output(repo, "rev-parse", REF)


def commit(repo, message):
    git(repo, "add", "--all")
    git(repo, "commit", "--quiet", "-m", message)
    return current(repo)


def candidate(repo, central_head, incoming):
    git(repo, "merge", "--no-ff", "--no-commit", incoming)
    tree = output(repo, "write-tree")
    git(repo, "merge", "--abort")
    return output(repo, "commit-tree", tree, "-p", central_head, "-p", incoming,
                  "-m", "reviewed candidate")


def registry_payload(offers, scope, generation, artifact, permissions):
    if scope not in permissions:
        return None
    blob = offers.get((scope, generation, artifact))
    if blob is None or sha256(blob).hexdigest() != artifact:
        return None
    return blob


def evaluate(repo, offer, expected, offers, permissions):
    head = current(repo)
    if offer["base"] != head:
        return "stale-target"
    if any(offer[field] != expected[field] for field in ("fork", "incoming", "candidate")):
        return "source-or-candidate-mismatch"
    line = output(repo, "rev-list", "--parents", "-n", "1", offer["candidate"]).split()
    if line[1:] != [head, offer["incoming"]]:
        return "merge-parents-mismatch"
    declared = json.loads(output(repo, "show", f"{offer['candidate']}:binding.json"))
    if (offer["registry"], offer["generation"], offer["artifact"]) != (
        declared["registry"], declared["generation"], declared["artifact"]
    ):
        return "registry-binding-mismatch"
    blob = registry_payload(offers, offer["registry"], offer["generation"], offer["artifact"], permissions)
    if blob is None:
        return "registry-unavailable"
    return "eligible"


def check(work):
    upstream = work / "upstream"
    upstream.mkdir()
    git(upstream, "init", "--quiet", "-b", "research/all", "--object-format=sha256")
    (upstream / "policy.txt").write_text("first policy\n")
    (upstream / "binding.json").write_text("{}\n")
    origin = commit(upstream, "fixture root")
    fork = work / "fork"
    git(work, "clone", "--quiet", "--no-local", upstream, fork)
    lock = {"registry": "registry:reviewed", "generation": 2, "artifact": ARTIFACT_HASH}
    (fork / "binding.json").write_text(json.dumps(lock, sort_keys=True) + "\n")
    incoming = commit(fork, "bind exact artifact")
    git(upstream, "fetch", "--quiet", fork, REF)
    assert output(upstream, "rev-parse", "FETCH_HEAD") == incoming and current(upstream) == origin
    old_candidate = candidate(upstream, origin, incoming)
    (upstream / "policy.txt").write_text("second policy\n")
    newest = commit(upstream, "advance target")
    merged = candidate(upstream, newest, incoming)
    assert old_candidate != merged
    assert output(upstream, "show", f"{merged}:policy.txt") == "second policy"

    accepted = {**lock, "base": newest, "fork": "fork:approved", "incoming": incoming, "candidate": merged}
    offers = {("registry:reviewed", 2, ARTIFACT_HASH): ARTIFACT,
              ("registry:reviewed", 1, OLD_ARTIFACT): b"retired fixture bytes",
              ("registry:other", 2, ARTIFACT_HASH): ARTIFACT}
    controls = {
        "retained_old_review": (dict(accepted, base=origin, candidate=old_candidate), offers, {"registry:reviewed"}),
        "wrong_fork_same_commit": (dict(accepted, fork="fork:other"), offers, {"registry:reviewed"}),
        "wrong_candidate": (dict(accepted, candidate=old_candidate), offers, {"registry:reviewed"}),
        "wrong_registry_same_bytes": (dict(accepted, registry="registry:other"), offers, {"registry:other"}),
        "wrong_generation": (dict(accepted, generation=1), offers, {"registry:reviewed"}),
        "grant_missing": (accepted, offers, set()),
        "missing_exact_payload": (accepted, {}, {"registry:reviewed"}),
        "payload_mismatch": (accepted, {("registry:reviewed", 2, ARTIFACT_HASH): b"other"}, {"registry:reviewed"}),
        "exact_input": (accepted, offers, {"registry:reviewed"}),
    }
    verdicts = {key: evaluate(upstream, offer, accepted, inventory, grants)
                for key, (offer, inventory, grants) in controls.items()}
    assert verdicts == {
        "retained_old_review": "stale-target", "wrong_fork_same_commit": "source-or-candidate-mismatch",
        "wrong_candidate": "source-or-candidate-mismatch", "wrong_registry_same_bytes": "registry-binding-mismatch",
        "wrong_generation": "registry-binding-mismatch", "grant_missing": "registry-unavailable",
        "missing_exact_payload": "registry-unavailable", "payload_mismatch": "registry-unavailable",
        "exact_input": "eligible",
    }
    old_parent_offer = {**accepted, "candidate": old_candidate}
    assert evaluate(upstream, old_parent_offer, old_parent_offer, offers, {"registry:reviewed"}) == (
        "merge-parents-mismatch")
    assert current(upstream) == newest
    stale_cas = git(upstream, "update-ref", REF, merged, origin, check=False)
    assert stale_cas.returncode != 0 and current(upstream) == newest
    git(upstream, "update-ref", REF, merged, newest)
    clone = work / "verification-clone"
    git(work, "clone", "--quiet", "--no-local", upstream, clone)
    assert current(clone) == merged
    assert json.loads(output(clone, "show", "HEAD:binding.json")) == lock
    return {"git": output(work, "--version"), "python": platform.python_version(),
            "original_target": origin, "expected_target": newest, "fork_commit": incoming,
            "first_candidate": old_candidate, "published_candidate": merged, "artifact_lock": lock,
            "published_parents": output(clone, "rev-list", "--parents", "-n", "1", merged).split()[1:],
            "gate_decisions": verdicts, "checked_clone": True,
            "wrong_parent_tree": "merge-parents-mismatch", "stale_ref_cas": "refused",
            "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    with TemporaryDirectory(prefix="rt24-registry-fork-") as temp:
        print(json.dumps(check(Path(temp)), sort_keys=True, indent=2))
