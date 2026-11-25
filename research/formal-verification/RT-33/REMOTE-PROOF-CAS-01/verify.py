"""Drive signed proof artifact leases, conflicts, GC and revocation over loopback HTTP."""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from http.client import HTTPConnection
import json
from pathlib import Path
import re
import runpy
from secrets import token_urlsafe
import sqlite3
from subprocess import check_output
from tempfile import TemporaryDirectory
from threading import Barrier, Event

from store import MAX_PAYLOAD, PRODUCERS, Refusal, Storage, digest, start

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PIN = "82bfc98e3e4ceeae7d2ce238918ddddfad0130da"
SUPPORT = ROOT / "research/toolchain-and-collaboration/RT-11/SIGNED-REBUILD-ADMISSION-01/run.py"
SIGNER = runpy.run_path(str(SUPPORT))


def request(server, token, method, path):
    client = HTTPConnection(*server, timeout=4)
    try:
        client.request(method, path, headers={"Authorization": token})
        response = client.getresponse()
        headers = dict(response.getheaders())
        body = response.read(4097)
        assert len(body) <= 4096 and int(headers["Content-Length"]) == len(body)
        return response.status, headers, body
    finally:
        client.close()


def unique(fields):
    result = {}
    for key, value in fields:
        if key in result:
            raise ValueError("duplicate field")
        result[key] = value
    return result


def unpack(wire, signers, project, claim, epoch):
    packet = json.loads(wire, object_pairs_hook=unique)
    if (not isinstance(packet, dict) or set(packet) != {"lease", "receipt", "signature"}
            or any(not isinstance(value, str) for value in packet.values())
            or not re.fullmatch(r"[A-Za-z0-9_-]{32}", packet["lease"])):
        raise ValueError("invalid lease envelope")
    receipt = json.loads(packet["receipt"], object_pairs_hook=unique)
    if (not isinstance(receipt, dict) or set(receipt) != {"project", "claim", "address", "epoch", "issuer"}
            or type(receipt["epoch"]) is not int or not isinstance(receipt["address"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", receipt["address"])):
        raise ValueError("invalid producer envelope")
    if (receipt["project"], receipt["claim"], receipt["epoch"]) != (project, claim, epoch):
        raise ValueError("incorrect signed scope")
    signed = SIGNER["Signed"](packet["receipt"].encode(), base64.b64decode(packet["signature"], validate=True))
    if (not isinstance(receipt["issuer"], str) or receipt["issuer"] not in PRODUCERS[project]
            or not signers.verify(signed, receipt["issuer"])):
        raise ValueError("invalid signature")
    return packet["lease"], receipt["address"]


def validate_body(response, address):
    status, headers, body = response
    if (status != 200 or headers["Content-Type"] != "application/octet-stream"
            or headers.get("ETag") != f'"{address}"' or not 0 < len(body) <= MAX_PAYLOAD
            or digest(body) != address):
        raise ValueError("unverified delivery")
    return body


def exercise(root):
    signer_path = root / "keys"
    signer_path.mkdir()
    signer = SIGNER["Signers"](signer_path)
    reader_a = "Bearer " + token_urlsafe(24)
    reader_b = "Bearer " + token_urlsafe(24)
    sessions = {reader_a: "reader-a", reader_b: "reader-b"}
    holders = {"alpha": reader_a, "beta": reader_b}
    checked = set()
    sql = root / "cache.sqlite"
    store = Storage(sql, signer, checked)
    with store.transaction() as db:
        assert db.execute("PRAGMA journal_mode = WAL").fetchone() == ("wal",)
    initial = {
        "shared": b"shared proof across two projects",
        "retained": b"retained until release",
        "expiry": b"retained until lease expiry",
        "revocation-race": b"no disclosure after the revocation linearizes",
        "known-read": b"already delivered to an authorized client",
        "corrupt": b"verify exact CAS on both sides",
    }

    def signed(project, claim, data, issuer="alice", epoch=1, *, independently_checked=True):
        address = digest(data)
        if independently_checked:
            checked.add((project, claim, address))
        return signer.sign({"project": project, "claim": claim, "address": address, "issuer": issuer, "epoch": epoch})

    for claim, body in initial.items():
        store.publish(signed("alpha", claim, body), body)
    store.publish(signed("beta", "shared", initial["shared"], "bob"), initial["shared"])
    with store.transaction() as db:
        assert db.execute("SELECT COUNT(*) FROM payload WHERE address = ?", (digest(initial["shared"]),)).fetchone() == (1,)

    outcomes = {}

    def reject_publish(name, value, data, reason):
        try:
            store.publish(value, data)
        except Refusal as error:
            assert error.reason == reason
            outcomes[name] = error.reason
        else:
            raise AssertionError(name)

    reject_publish("signed-unknown-check", signed("alpha", "unsupported", b"none", independently_checked=False),
                   b"none", "no-independent-check")
    reject_publish("unauthorized-producer", signed("beta", "unexpected", b"same"),
                   b"same", "publisher-or-payload")
    wrong = signed("alpha", "unproven", b"bytes")
    reject_publish("tampered-publication-signature", replace(wrong, signature=wrong.signature[:-1]),
                   b"bytes", "publisher-or-payload")

    blocked, release = Event(), Event()
    held = set()

    def pause(handle):
        if handle in held:
            blocked.set()
            assert release.wait(3)

    def issue(server, project, claim, epoch=1):
        status, headers, body = request(server, holders[project], "POST", f"/v1/lease/{project}/{claim}")
        assert status == 201 and headers["Content-Type"] == "application/json", body
        return unpack(body, signer, project, claim, epoch), body

    def fetch(server, handle, project="alpha"):
        return request(server, holders[project], "GET", f"/v1/payload/{handle}")

    def reject_http(name, response, expected, reason):
        code, headers, data = response
        assert code == expected and headers["Content-Type"] == "application/json"
        assert json.loads(data) == {"code": reason}, (name, data)
        outcomes[name] = reason

    def bad_packet(wire):
        try:
            unpack(wire, signer, "alpha", "shared", 1)
        except ValueError:
            return "refused"
        raise AssertionError("malformed packet accepted")

    with start(store, sessions, pause) as server:
        (alpha, address), packet = issue(server, "alpha", "shared")
        (beta, second_address), _ = issue(server, "beta", "shared")
        assert address == second_address and alpha != beta
        assert validate_body(fetch(server, alpha), address) == validate_body(fetch(server, beta, "beta"), address)
        outcomes["same-payload-two-scoped-receipts"] = "checked"
        reject_http("other-project-discovery",
                    request(server, reader_b, "POST", "/v1/lease/alpha/shared"), 403, "not-authorized")
        reject_http("other-audience-lease", fetch(server, alpha, "beta"), 403, "lease-unavailable")
        reject_http("unknown-session", request(server, "Bearer other", "POST", "/v1/lease/alpha/shared"),
                    403, "not-authorized")
        outcomes["duplicate-wire-field"] = bad_packet(packet.replace(b'"lease":', b'"lease": "duplicate", "lease":', 1))
        changed_packet = json.loads(packet)
        changed_packet["signature"] = "AA=="
        outcomes["client-rejects-unauthenticated-wire-receipt"] = bad_packet(json.dumps(changed_packet).encode())
        response = fetch(server, alpha)
        try:
            validate_body((response[0], response[1], response[2] + b"changed"), address)
        except ValueError:
            outcomes["client-detects-changed-transport-bytes"] = "refused"
        else:
            raise AssertionError("changed delivery accepted")

        for claim, order in (("conflict-ab", ("alice", "bob")), ("conflict-ba", ("bob", "alice"))):
            handles = {}
            for issuer in order:
                data = f"proof written by {issuer}".encode()
                store.publish(signed("alpha", claim, data, issuer), data)
                if issuer == order[0]:
                    handles[claim] = issue(server, "alpha", claim)[0][0]
            reject_http(claim, request(server, reader_a, "POST", f"/v1/lease/alpha/{claim}"),
                        409, "authorized-conflict")
            reject_http(claim + "-old-lease", fetch(server, handles[claim]), 409, "authorized-conflict")

        barrier = Barrier(2)
        queued = [(signed("alpha", "concurrent", body, issuer), body)
                  for issuer, body in (("alice", b"proof-a"), ("bob", b"proof-b"))]

        def publish_race(item):
            barrier.wait(timeout=2)
            store.publish(*item)

        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(publish_race, queued))
        reject_http("concurrent-publication", request(server, reader_a, "POST", "/v1/lease/alpha/concurrent"),
                    409, "authorized-conflict")

        (kept, kept_address), _ = issue(server, "alpha", "retained")
        store.remove_candidate("alpha", "retained")
        with ThreadPoolExecutor(max_workers=2) as executor:
            remote = executor.submit(fetch, server, kept)
            gc = executor.submit(store.collect)
            assert validate_body(remote.result(), kept_address) == initial["retained"]
            assert kept_address not in gc.result()
        outcomes["concurrent-gc-retains-live-lease"] = "checked"
        store.release(kept)
        assert kept_address in store.collect()
        reject_http("released-and-collected", fetch(server, kept), 403, "lease-unavailable")

        (expires, expires_address), _ = issue(server, "alpha", "expiry")
        store.remove_candidate("alpha", "expiry")
        assert expires_address not in store.collect()
        store.advance(4)
        assert expires_address in store.collect()
        reject_http("expired-and-collected", fetch(server, expires), 403, "lease-unavailable")

        (corrupt, corrupt_address), _ = issue(server, "alpha", "corrupt")
        with store.transaction() as db:
            db.execute("UPDATE payload SET body = ? WHERE address = ?", (b"wrong", corrupt_address))
        reject_http("server-detects-corrupt-cas", fetch(server, corrupt), 409, "payload-integrity")

        (prior, prior_address), _ = issue(server, "alpha", "known-read")
        previously_delivered = validate_body(fetch(server, prior), prior_address)
        (raced, _), _ = issue(server, "alpha", "revocation-race")
        held.add(raced)
        with ThreadPoolExecutor(max_workers=1) as executor:
            pending = executor.submit(fetch, server, raced)
            assert blocked.wait(3)
            store.revoke("alpha", "reader-a")
            release.set()
            revoked_result = pending.result()
        reject_http("revocation-after-preflight", revoked_result, 403, "not-authorized")
        reject_http("revocation-after-delivery", fetch(server, prior), 403, "not-authorized")
        assert previously_delivered == initial["known-read"]

        store.restore("alpha", "reader-a")
        reject_http("restored-reader-old-grant", fetch(server, raced), 403, "lease-unavailable")
        reject_http("new-lease-requires-current-receipt",
                    request(server, reader_a, "POST", "/v1/lease/alpha/known-read"), 404, "candidate-unavailable")
        body = initial["known-read"]
        reject_publish("old-publisher-epoch", signed("alpha", "known-read", body), body, "stale-publication-policy")
        store.publish(signed("alpha", "known-read", body, epoch=2), body)
        (fresh, fresh_address), _ = issue(server, "alpha", "known-read", epoch=2)
        assert validate_body(fetch(server, fresh), fresh_address) == body
        outcomes["new-grant-and-current-signed-receipt"] = "checked"

    restarted = Storage(sql, signer, checked, setup=False)
    with start(restarted, sessions) as server:
        assert validate_body(fetch(server, fresh), fresh_address) == initial["known-read"]
        reject_http("expired-lease-after-restart", fetch(server, expires), 403, "lease-unavailable")
    outcomes["recorded-receipt-and-lease-survive-restart"] = "checked"
    return {"observations": outcomes, "observation_count": len(outcomes), "sqlite": sqlite3.sqlite_version,
            "openssl": check_output(["/usr/bin/openssl", "version"], text=True).strip()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    options = parser.parse_args()
    location = SUPPORT.relative_to(ROOT).as_posix()
    exact = check_output(["git", "show", f"{PIN}:{location}"], cwd=ROOT)
    assert SUPPORT.read_bytes() == exact
    with TemporaryDirectory() as scratch:
        result = exercise(Path(scratch))
    options.output.write_text(json.dumps({"basis": PIN, "signer_sha256": digest(exact), **result},
                                        sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
