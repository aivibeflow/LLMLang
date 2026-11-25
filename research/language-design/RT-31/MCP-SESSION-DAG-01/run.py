"""Run two independent MCP stdio repair sessions and verify event correlation."""
import argparse
from dataclasses import asdict, replace
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import random
import select
import subprocess
import sys
from urllib.parse import urlsplit

from events import Scope, digest, event, verify

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parents[2]
THEME = RESEARCH / "toolchain-and-collaboration"
SERVER = THEME / "RT-19" / "MCP-STDIO-01" / "server.py"
DOMAIN = THEME / "PROTOTYPES" / "TOOLCHAIN-SERVER-01" / "toolchain.py"


def request(process, identifier, method, parameters=None):
    data = {"jsonrpc": "2.0", "method": method}
    if parameters is not None:
        data["params"] = parameters
    if identifier is not None:
        data["id"] = identifier
    process.stdin.write(json.dumps(data) + "\n")
    process.stdin.flush()
    if identifier is None:
        return None
    readable, _, _ = select.select([process.stdout], [], [], 10)
    if not readable:
        raise TimeoutError(method)
    response = json.loads(process.stdout.readline())
    assert response["id"] == identifier and response["jsonrpc"] == "2.0"
    return response["result"]


def call(process, identifier, tool, arguments):
    return request(process, identifier, "tools/call", {"name": tool, "arguments": arguments})


def query_session(process, label, value):
    hello = request(process, 1, "initialize", {"protocolVersion": "2025-11-25"})
    assert hello["protocolVersion"] == "2025-11-25"
    request(process, None, "notifications/initialized")
    resources = request(process, 2, "resources/list")["resources"]
    baseline = urlsplit(resources[0]["uri"]).path.split("/")[1]
    mapping = {}
    for identifier, row in enumerate(resources, start=3):
        resource = request(process, identifier, "resources/read", {"uri": row["uri"]})
        body = json.loads(resource["contents"][0]["text"])
        mapping[body["stable_id"]] = body["content_hash"]
        assert body["content_hash"] == "sha256:" + digest({"kind": body["kind"], "payload": body["payload"]})
    assert "sha256:" + digest({"format_version": 1, "entities": mapping}) == baseline
    workspace = call(process, 5, "open_workspace", {"snapshot_id": baseline})["structuredContent"]
    assert workspace["working_snapshot"] == baseline and workspace["revision"] == 0
    plan = {
        "workspace_id": workspace["workspace_id"],
        "changeset_id": label + "-patch",
        "changes": [{"action": "add", "stable_id": "item:fixture", "expected_hash": None,
                     "kind": "module", "payload": {"value": value}}],
    }
    bad = call(process, 6, "apply_change_set", {**plan, "expected_revision": 9})
    assert bad["isError"] and json.loads(bad["content"][0]["text"]) == {"code": "StaleRevision"}
    unchanged = call(process, 7, "inspect_workspace", {"workspace_id": workspace["workspace_id"]})
    assert unchanged["structuredContent"] == workspace
    good = call(process, 8, "apply_change_set", {**plan, "expected_revision": 0})
    assert not good["isError"] and good["structuredContent"]["revision"] == 1
    mapping["item:fixture"] = "sha256:" + digest({"kind": "module", "payload": {"value": value}})
    expected_root = "sha256:" + digest({"format_version": 1, "entities": mapping})
    assert good["structuredContent"]["working_snapshot"] == expected_root

    adapter = digest({"protocol": hello["protocolVersion"],
                      "server": sha256(SERVER.read_bytes()).hexdigest(),
                      "domain": sha256(DOMAIN.read_bytes()).hexdigest()})
    scope = Scope(label, baseline, adapter)
    start = event(scope, "session", "opened")
    turn = event(scope, "turn", "opened", turn=1, parent=start)
    attempt = event(scope, "attempt", "opened", turn=1, attempt=1, parent=turn)
    records = [start, turn, attempt]
    for number, wire, result_root, allowed in ((1, 6, baseline, False), (2, 8, expected_root, True)):
        parent = records[-1]
        request_event = event(scope, "request", "issued", turn=1, attempt=number, wire=wire, parent=parent)
        outcome = "ok" if allowed else "refused"
        response = event(scope, "response", outcome, turn=1, attempt=number, wire=wire,
                         result_root=result_root, parent=request_event)
        tool = event(scope, "tool", outcome, turn=1, attempt=number, wire=wire,
                     result_root=result_root, parent=response)
        validation = event(scope, "validation", "passed" if allowed else "failed", turn=1,
                           attempt=number, wire=wire, result_root=result_root, parent=tool)
        settlement = (event(scope, "terminal", "complete", turn=1, attempt=number,
                            result_root=result_root, parent=validation) if allowed else
                      event(scope, "repair", "opened", turn=1, attempt=2, parent=validation))
        records += [request_event, response, tool, validation, settlement]
    return scope, expected_root, records


def run_session(label, value):
    with subprocess.Popen([sys.executable, "-B", SERVER], text=True, stderr=subprocess.PIPE,
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE) as process:
        try:
            outcome = query_session(process, label, value)
            process.stdin.close()
            status = process.wait(timeout=10)
            assert status == 0, process.stderr.read()
            return outcome
        finally:
            if process.poll() is None:
                process.kill()


def assess():
    left_scope, left_root, left = run_session("session-a", 21)
    right_scope, right_root, right = run_session("session-b", 34)
    assert left_scope.baseline == right_scope.baseline and left_root != right_root
    records = left + right
    expected = {left_scope.session: (left_scope, left_root), right_scope.session: (right_scope, right_root)}
    assert verify(records, expected) == "complete"
    assert len({row.identity for row in records}) == 26
    rng = random.Random(342)
    for _ in range(48):
        order = records[:]
        rng.shuffle(order)
        assert verify(order, expected) == "complete"
        assert verify(order[:12], expected) == "pending"

    def get(history, kind, attempt):
        return next(row for row in history if row.kind == kind and row.attempt == attempt)

    response = get(left, "response", 1)
    other_request = get(right, "request", 1)
    repair_request = get(left, "request", 2)
    earlier = get(left, "validation", 1)
    final = get(left, "terminal", 2)
    repair = get(left, "repair", 2)
    cases = {
        "exact_redelivery": records + [response],
        "conflicting_same_slot": records + [replace(response, outcome="ok")],
        "cross_session_same_wire": [replace(row, parent=other_request.identity) if row is response else row
                                    for row in records],
        "wire_reuse_within_session": [replace(row, wire=response.wire) if row is repair_request else row
                                       for row in records],
        "wrong_wire_id": [replace(row, wire=9) if row is response else row for row in records],
        "wrong_producer": [replace(row, actor="client") if row is response else row for row in records],
        "wrong_adapter_revision": [replace(row, scope=replace(row.scope, adapter="different"))
                                   if row is response else row for row in records],
        "missing_repair": [row for row in records if row is not repair],
        "terminal_uses_failed_attempt": [replace(row, parent=earlier.identity) if row is final else row
                                         for row in records],
    }
    received = {name: verify(events, expected) for name, events in cases.items()}
    assert received == {
        "exact_redelivery": "complete", "conflicting_same_slot": "refused-conflicting-event",
        "cross_session_same_wire": "refused-causal-edge", "wrong_wire_id": "refused-causal-edge",
        "wire_reuse_within_session": "refused-wire-reuse",
        "wrong_producer": "refused-scope-or-schema", "wrong_adapter_revision": "refused-scope-or-schema",
        "missing_repair": "pending", "terminal_uses_failed_attempt": "refused-causal-edge",
    }, received
    return {
        "protocol": "2025-11-25", "jsonschema": version("jsonschema"),
        "sessions": 2, "mutation_requests": 4,
        "versioned_events": len(records), "complete_delivery_orders": 48,
        "partial_delivery_controls": 48, "controls": received,
        "ledger": [{"identity": row.identity, **asdict(row)} for row in records],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(assess(), indent=2) + "\n")


if __name__ == "__main__":
    main()
