#!/usr/bin/env python3
"""Check defensive, exact cache admission with local fixture signers and native rebuilds."""

from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import permutations
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

ENV = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "LANG": "C"}
SOURCE = b"int value(void) { return 17; }\n"
OTHER = b"int value(void) { return 29; }\n"
FLAGS = ("-std=c11", "-O2", "-Werror", "-c", "unit.c", "-o", "unit.o")


def digest(data):
    return sha256(data).hexdigest()


def encoded(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()


def run(args, root, *, check=True):
    return subprocess.run(args, cwd=root, env=ENV, capture_output=True, check=check)


def build(root, name, source):
    work = root / name
    work.mkdir()
    (work / "unit.c").write_bytes(source)
    run(["gcc", *FLAGS], work)
    return (work / "unit.o").read_bytes()


@dataclass(frozen=True)
class Signed:
    message: bytes
    signature: bytes


class Signers:
    def __init__(self, root):
        self.root = root
        self.trust = {}
        for name in ("alice", "bob", "visitor"):
            run(["openssl", "genpkey", "-algorithm", "ED25519", "-out", f"{name}.private"], root)
            run(["openssl", "pkey", "-in", f"{name}.private", "-pubout", "-out", f"{name}.public"], root)
            self.trust[name] = f"{name}.public"

    def sign(self, data):
        message = encoded(data)
        (self.root / "message").write_bytes(message)
        signature = run([
            "openssl", "pkeyutl", "-sign", "-inkey", f"{data['issuer']}.private",
            "-rawin", "-in", "message",
        ], self.root).stdout
        return Signed(message, signature)

    def verify(self, signed, issuer):
        if issuer not in self.trust:
            return False
        (self.root / "message").write_bytes(signed.message)
        (self.root / "signature").write_bytes(signed.signature)
        result = run([
            "openssl", "pkeyutl", "-verify", "-pubin", "-inkey", self.trust[issuer],
            "-rawin", "-in", "message", "-sigfile", "signature",
        ], self.root, check=False)
        return result.returncode == 0


@dataclass(frozen=True)
class Request:
    key: str
    closure: str
    workspace: str
    policy_generation: int
    issuers: frozenset[str]


def admit(request, signed_records, signers, store, rebuild, *, complete):
    if not complete:
        return "view-unavailable", ()
    addresses = set()
    for signed in set(signed_records):
        row = json.loads(signed.message)
        if not signers.verify(signed, row["issuer"]):
            continue
        if (
            row["scheme"], row["action"], row["closure"], row["workspace"], row["generation"]
        ) != ("native-cache-attestation/1", request.key, request.closure,
              request.workspace, request.policy_generation):
            continue
        if row["issuer"] in request.issuers:
            addresses.add(row["artifact"])
    candidates = tuple(sorted(addresses))
    if not candidates:
        return "no-attestation", candidates
    if len(candidates) > 1:
        return "conflict", candidates
    address, = candidates
    if address not in store:
        return "payload-unavailable", candidates
    if digest(store[address]) != address:
        return "payload-refused", candidates
    if rebuild is None:
        return "rebuild-unavailable", candidates
    if digest(rebuild) != address:
        return "rebuild-disagrees", candidates
    return "exact-hit", candidates


def experiment(root):
    expected = build(root, "producer", SOURCE)
    replay = build(root, "replayer", SOURCE)
    rebuilt_again = build(root, "fresh-rebuild", SOURCE)
    wrong = build(root, "independent-alternative", OTHER)
    assert expected == replay == rebuilt_again and wrong != expected
    compiler = shutil.which("gcc", path=ENV["PATH"])
    tool = {
        "version": run(["gcc", "-dumpfullversion"], root).stdout.decode().strip(),
        "digest": digest(Path(compiler).read_bytes()),
        "target": run(["gcc", "-dumpmachine"], root).stdout.decode().strip(),
    }
    closure = digest(encoded({"translation_unit": digest(SOURCE), "includes": []}))
    action = digest(encoded({
        "runner": tool, "argv": FLAGS, "environment": ENV,
        "closure": closure, "workspace": "fixture-root",
    }))
    signers = Signers(root)
    addresses = {"expected": digest(expected), "other": digest(wrong)}
    policy = Request(action, closure, "workspace-A", 4, frozenset({"alice", "bob"}))
    template = {
        "scheme": "native-cache-attestation/1", "action": action, "closure": closure,
        "workspace": policy.workspace, "generation": 4, "artifact": addresses["expected"],
    }
    alternate = template | {"artifact": addresses["other"]}
    receipts = {
        name: signers.sign(data | {"issuer": issuer})
        for name, data, issuer in (
            ("alice", template, "alice"),
            ("bob-agrees", template, "bob"),
            ("bob-disagrees", alternate, "bob"),
            ("visitor", alternate, "visitor"),
            ("older-generation", template | {"generation": 3}, "alice"),
            ("other-workspace", template | {"workspace": "workspace-B"}, "alice"),
            ("other-closure", template | {"closure": digest(b"another declared closure")}, "alice"),
            ("other-action", template | {"action": digest(b"another action")}, "alice"),
        )
    }
    receipts["changed-message"] = replace(
        receipts["alice"], message=encoded(alternate | {"issuer": "alice"})
    )
    receipts["bad-signature"] = replace(receipts["alice"], signature=b"\x00" * 64)
    for name, signed in receipts.items():
        issuer = json.loads(signed.message)["issuer"]
        assert signers.verify(signed, issuer) == (name not in {"changed-message", "bad-signature"})

    clean = {addresses["expected"]: expected, addresses["other"]: wrong}
    unavailable = {addresses["expected"]: expected}
    corrupt = clean | {addresses["expected"]: wrong}
    only_alice = replace(policy, issuers=frozenset({"alice"}))
    cases = (
        ("agree", ("alice", "bob-agrees"), policy, clean, replay, True, "exact-hit"),
        ("duplicate", ("alice", "alice"), policy, clean, replay, True, "exact-hit"),
        ("untrusted-view-incomplete", ("alice",), policy, clean, replay, False, "view-unavailable"),
        ("conflict", ("alice", "bob-disagrees"), policy, clean, replay, True, "conflict"),
        ("conflict-with-missing-alternative", ("alice", "bob-disagrees"), policy, unavailable, replay, True, "conflict"),
        ("explicit-revocation", ("alice", "bob-disagrees"), only_alice, clean, replay, True, "exact-hit"),
        ("untrusted-signer", ("visitor",), policy, clean, replay, True, "no-attestation"),
        ("untrusted-cannot-conflict", ("alice", "visitor"), policy, clean, replay, True, "exact-hit"),
        ("stale-policy", ("older-generation",), policy, clean, replay, True, "no-attestation"),
        ("wrong-workspace", ("other-workspace",), policy, clean, replay, True, "no-attestation"),
        ("wrong-closure", ("other-closure",), policy, clean, replay, True, "no-attestation"),
        ("wrong-action", ("other-action",), policy, clean, replay, True, "no-attestation"),
        ("changed-message", ("changed-message",), policy, clean, replay, True, "no-attestation"),
        ("bad-signature", ("bad-signature",), policy, clean, replay, True, "no-attestation"),
        ("no-payload", ("alice",), policy, {}, replay, True, "payload-unavailable"),
        ("wrong-bytes", ("alice",), policy, corrupt, replay, True, "payload-refused"),
        ("no-independent-rebuild", ("alice",), policy, clean, None, True, "rebuild-unavailable"),
        ("signed-disagrees-with-rebuild", ("bob-disagrees",), policy, clean, replay, True, "rebuild-disagrees"),
    )
    rows = []
    for name, labels, active, store, rebuilt, complete, expected_result in cases:
        decision, candidates = admit(active, [receipts[label] for label in labels], signers, store, rebuilt,
                                     complete=complete)
        assert decision == expected_result
        rows.append({
            "name": name, "attestations": labels, "decision": decision,
            "authorized_results": candidates,
        })
    mixed = ("alice", "bob-agrees", "bob-disagrees", "visitor", "changed-message")
    for order in permutations(mixed):
        result = admit(policy, [receipts[label] for label in order], signers, clean, replay, complete=True)
        assert result == ("conflict", tuple(sorted(addresses.values())))
    return {
        "format": "signed-rebuild-admission-01",
        "tool": tool, "openssl": run(["openssl", "version"], root).stdout.decode().strip(),
        "input_closure": closure, "action": action, "artifacts": addresses,
        "exact_rebuilds": 3, "candidate_orders": 120, "rows": rows,
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-cache-signing-") as directory:
        ledger = experiment(Path(directory))
    text = json.dumps(ledger, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
