#!/usr/bin/env python3
"""Compare stale and revalidated export publication over separate native Git refs."""

from collections import Counter
from hashlib import sha256
import importlib.util
from itertools import product
import json
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "CROSS-MAP-EXPORT-01" / "run.py"
spec = importlib.util.spec_from_file_location("closed_export_fixture", PRIOR)
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)

BINDING = "refs/heads/binding"
EXPORT = "refs/heads/export"
BACKENDS = ("files", "reftable")
POLICIES = ("old_own_only", "strict_refs", "fresh_unverified", "fresh_verified")
CASES = (
    "abi_incompatible", "new_scope_unknown", "new_scope_certified", "unrelated_export",
    "second_peer_move", "same_content_new_history",
)


def git(repo, *args):
    return prior.git(repo, *args)


def transaction(repo, ours, new, old, peer=None):
    commands = ["start", f"update {ours} {new} {old}"]
    if peer:
        commands.append(f"verify {peer[0]} {peer[1]}")
    commands.extend(["prepare", "commit"])
    data = ("\n".join(commands) + "\n").encode()
    try:
        raw = prior.git_fixture.git(repo, "update-ref", "--stdin", stdin=data)
    except subprocess.CalledProcessError as error:
        message = error.stderr.decode()
        assert "is at" in message and "but expected" in message
        return {"status": "stale", "native_exit": error.returncode, "commands": commands}
    assert raw.decode().splitlines() == ["start: ok", "prepare: ok", "commit: ok"]
    return {"status": "committed", "native_exit": 0, "commands": commands}


def current(repo, ref):
    return git(repo, "rev-parse", ref)


def check(repo, binding, export):
    artifacts = prior.read_json(repo, binding, prior.ARTIFACTS)
    store = prior.admit_artifacts(artifacts)
    bindings = prior.read_json(repo, binding, prior.BINDINGS)
    names = prior.read_json(repo, export, prior.NAMES)
    exports = prior.read_json(repo, export, prior.EXPORTS)
    receipts = prior.read_json(repo, binding, prior.LEFT) + prior.read_json(repo, export, prior.RIGHT)
    evidence = []
    for declaration in exports:
        op = names[declaration["public_name"]]
        contract = store.get(op).payload["contract"]
        provider = bindings[op]
        key = prior.exact_key(op, contract, provider, declaration)
        exact = [row for row in receipts if tuple(row["claim"]) == key]
        try:
            digest = prior.proof_body(store, key)
        except ValueError:
            status = "incompatible"
        else:
            status = "admitted" if any(row["test_vector_digest"] == digest for row in exact) else "unknown"
        evidence.append({"symbol": declaration["symbol"], "exact_key": key, "status": status})
    verdict = next((row["status"] for row in evidence if row["status"] != "admitted"), "admitted")
    return {"status": verdict, "selection": evidence, "binding_oid": binding, "export_oid": export}


def prepare(repo, backend, case):
    git(repo, "init", "--quiet", "--template=", "--initial-branch=base", "--object-format=sha1",
        f"--ref-format={backend}")
    assert git(repo, "rev-parse", "--show-ref-format") == backend
    artifacts, contract, operations, providers = prior.encode_artifacts()
    store = prior.admit_artifacts(artifacts)
    entry = prior.export("public/entry")
    dormant = prior.export("public/dormant", symbol="dormant")
    initial_bindings = dict.fromkeys(operations.values(), providers["default"])

    def receipt(role, provider, selection):
        return prior.certificate(store, prior.exact_key(operations[role], contract, providers[provider], selection))

    base = prior.git_fixture.commit(repo, {
        prior.ARTIFACTS: artifacts, prior.NAMES: {f"public/{role}": op for role, op in operations.items()},
        prior.BINDINGS: initial_bindings, prior.EXPORTS: [entry],
        prior.LEFT: [], prior.RIGHT: [receipt("entry", "default", entry)],
        "reason.txt": "original export generation\n",
    })
    git(repo, "update-ref", BINDING, base)
    git(repo, "update-ref", EXPORT, base)
    git(repo, "switch", "--quiet", "--detach", base)
    changed_to = "narrow_abi" if case in {"abi_incompatible", "second_peer_move"} else "portable"
    replacement = prior.git_fixture.commit(repo, {
        prior.BINDINGS: {**initial_bindings, operations["entry"]: providers[changed_to]},
        prior.LEFT: [receipt("entry", changed_to, entry)],
    })
    git(repo, "switch", "--quiet", "--detach", base)
    new_abi = {**entry, "abi": "b"}
    withdrawn = None
    if case == "unrelated_export":
        effects = [entry, dormant]
        rights = [receipt("entry", "default", entry), receipt("dormant", "default", dormant)]
    elif case == "second_peer_move":
        renamed = {**entry, "symbol": "renamed"}
        effects = [renamed]
        rights = [receipt("entry", "default", renamed)]
    elif case == "same_content_new_history":
        effects = [entry]
        rights = [receipt("entry", "default", entry)]
        withdrawn = prior.git_fixture.commit(repo, {prior.EXPORTS: [], "reason.txt": "withdraw export\n"})
    else:
        effects = [new_abi]
        rights = [receipt("entry", "default", new_abi)]
        if case == "new_scope_certified":
            rights.append(receipt("entry", "portable", new_abi))
    next_peer = prior.git_fixture.commit(repo, {
        prior.EXPORTS: effects, prior.RIGHT: rights, "reason.txt": "peer export generation\n",
    })
    final_peer = None
    if case == "second_peer_move":
        final_peer = prior.git_fixture.commit(repo, {
            prior.EXPORTS: [new_abi], prior.RIGHT: [receipt("entry", "default", new_abi)],
            "reason.txt": "second peer export generation\n",
        })
    elif case == "same_content_new_history":
        assert prior.read_json(repo, base, prior.EXPORTS) == prior.read_json(repo, next_peer, prior.EXPORTS)
        assert git(repo, "rev-parse", f"{base}:{prior.EXPORTS}") == git(repo, "rev-parse", f"{next_peer}:{prior.EXPORTS}")
        assert base != next_peer
    assert check(repo, replacement, base)["status"] == "admitted"
    assert check(repo, base, next_peer)["status"] == "admitted"
    if final_peer:
        assert check(repo, base, final_peer)["status"] == "admitted"
    return base, replacement, next_peer, final_peer, withdrawn


def scenario(repo, backend, case, policy):
    base, replacement, next_peer, final_peer, withdrawn = prepare(repo, backend, case)
    original = check(repo, replacement, base)
    assert current(repo, BINDING) == current(repo, EXPORT) == base
    events = [{"decision": "initial", "evidence": original}]
    expected_export = base
    if withdrawn:
        removal = transaction(repo, EXPORT, withdrawn, base)
        assert removal["status"] == "committed" and current(repo, EXPORT) == withdrawn
        observed_withdrawal = check(repo, base, withdrawn)
        assert observed_withdrawal["selection"] == []
        events.append({"peer_temporarily_withdraws_export": removal, "observed": observed_withdrawal})
        expected_export = withdrawn
    first = transaction(repo, EXPORT, next_peer, expected_export)
    assert first["status"] == "committed"
    events.append({"peer_write": first})

    def late_peer():
        if final_peer and current(repo, EXPORT) != final_peer:
            result = transaction(repo, EXPORT, final_peer, next_peer)
            assert result["status"] == "committed"
            events.append({"peer_write_after_check": result})

    if policy in {"old_own_only", "strict_refs"}:
        peer = (EXPORT, base) if policy == "strict_refs" else None
        late_peer()
        events.append({"publisher_write": transaction(repo, BINDING, replacement, base, peer)})
    else:
        for attempt in range(2):
            head = current(repo, EXPORT)
            evidence = check(repo, replacement, head)
            events.append({"decision": "fresh", "evidence": evidence})
            if evidence["status"] != "admitted":
                break
            late_peer()
            peer = (EXPORT, head) if policy == "fresh_verified" else None
            outcome = transaction(repo, BINDING, replacement, base, peer)
            events.append({"publisher_write": outcome})
            if outcome["status"] == "committed":
                break
            assert policy == "fresh_verified" and final_peer and attempt == 0

    final_binding, final_export = current(repo, BINDING), current(repo, EXPORT)
    final = check(repo, final_binding, final_export)
    intended = check(repo, replacement, final_export)
    admitted = final_binding == replacement
    assert final_export == (final_peer or next_peer)
    assert final_binding in {base, replacement}
    expected_valid = case in {"new_scope_certified", "unrelated_export", "same_content_new_history"}
    assert (intended["status"] == "admitted") == expected_valid
    assert admitted == {
        "old_own_only": True, "strict_refs": False,
        "fresh_unverified": expected_valid or bool(final_peer), "fresh_verified": expected_valid,
    }[policy]
    assert (final["status"] == "admitted") == (expected_valid or not admitted)
    if case == "second_peer_move" and policy == "fresh_verified":
        assert [row["publisher_write"]["status"] for row in events if "publisher_write" in row] == ["stale"]
        assert events[-1]["evidence"]["status"] == "incompatible"

    return {"backend": backend, "case": case, "policy": policy, "events": events,
            "intended_at_final_peer": intended, "final": final, "published": admitted,
            "valid_proposal_refused": expected_valid and not admitted,
            "ineligible_publication": admitted and not expected_valid}


def run(directory):
    version = subprocess.check_output(["git", "--version"], text=True).strip()
    assert version == "git version 2.52.0", version
    cases = []
    for backend, case, policy in product(BACKENDS, CASES, POLICIES):
        repo = directory / f"{backend}-{case}-{policy}"
        repo.mkdir()
        cases.append(scenario(repo, backend, case, policy))
    for case, policy in product(CASES, POLICIES):
        rows = [{key: value for key, value in row.items() if key != "backend"}
                for row in cases if row["case"] == case and row["policy"] == policy]
        assert rows[0] == rows[1]
    metrics = {}
    for policy in POLICIES:
        counters = Counter()
        for row in cases:
            if row["policy"] == policy:
                for field in ("published", "valid_proposal_refused", "ineligible_publication"):
                    counters[field] += row[field]
        metrics[policy] = dict(counters)
    return {
        "schema": "llmlang-rt24-cross-map-refs/1", "git": version, "python": platform.python_version(),
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "prior_fixture_sha256": sha256(PRIOR.read_bytes()).hexdigest(), "case_count": len(cases),
        "metrics": metrics, "cases": cases,
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-rt24-cross-map-refs-") as scratch:
        result = run(Path(scratch))
    cases = result.pop("cases")
    print(json.dumps(result, indent=2).removesuffix("\n}") + ',\n  "cases": [')
    print(",\n".join("    " + json.dumps(row) for row in cases))
    print("  ]\n}")
