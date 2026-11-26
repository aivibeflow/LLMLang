"""Exercise llmlang-server through its MCP stdio protocol.

Run with the built server executable as the first argument. The server process
inherits the verifier and compiler tool paths from the test environment.
"""

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import tempfile
import time


class Client:
    def __init__(self, process):
        self.process = process
        self.next_id = 1
        self.pending = bytearray()
        self.selector = selectors.DefaultSelector()
        self.selector.register(process.stdout, selectors.EVENT_READ)

    def send(self, message):
        encoded = json.dumps({"jsonrpc": "2.0", **message}).encode("utf-8")
        self.process.stdin.write(encoded + b"\n")
        self.process.stdin.flush()

    def receive(self):
        deadline = time.monotonic() + 180
        while b"\n" not in self.pending:
            wait = deadline - time.monotonic()
            if wait <= 0 or not self.selector.select(wait):
                raise AssertionError("the server did not respond before the deadline")
            data = os.read(self.process.stdout.fileno(), 8192)
            if not data:
                raise AssertionError(f"the server closed stdout (status {self.process.poll()})")
            self.pending.extend(data)
        line, _, remaining = self.pending.partition(b"\n")
        self.pending = remaining
        return json.loads(line)

    def request(self, method, **params):
        request_id = self.next_id
        self.next_id += 1
        self.send({"id": request_id, "method": method, "params": params})
        response = self.receive()
        assert response.get("jsonrpc") == "2.0", response
        assert response.get("id") == request_id, response
        assert "error" not in response, response
        return response["result"]

    def initialize(self):
        result = self.request(
            "initialize",
            protocolVersion="2025-11-25",
            capabilities={},
            clientInfo={"name": "llmlang-server-e2e", "version": "1.0.0"},
        )
        assert "tools" in result["capabilities"], result
        assert "resources" in result["capabilities"], result
        self.send({"method": "notifications/initialized"})
        assert self.request("ping") == {}

    def call(self, name, arguments, *, succeeds=True):
        result = self.request("tools/call", name=name, arguments=arguments)
        assert result.get("isError", False) == (not succeeds), (name, result)
        if succeeds:
            assert "structuredContent" in result, result
            return result["structuredContent"]
        if "structuredContent" in result:
            return result["structuredContent"]
        return json.loads(result["content"][0]["text"])


@contextmanager
def server(executable, state_dir, python):
    with tempfile.TemporaryFile() as stderr, subprocess.Popen(
        [str(executable), "--state-dir", str(state_dir), "--python", python],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=stderr,
    ) as process:
        client = Client(process)
        try:
            client.initialize()
            yield client
        except Exception:
            stderr.seek(0)
            diagnostic = stderr.read().decode("utf-8", errors="replace").strip()
            if diagnostic:
                print(diagnostic, file=sys.stderr)
            raise
        finally:
            client.selector.close()
            process.stdin.close()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def local(name):
    return {"local": name}


SIGNATURE = {"params": [], "result": "i64"}


def implementation(name, body, contract):
    return {
        "op": "put_function",
        "id": name,
        "typed_signature": SIGNATURE,
        "canonical_body": [["return", body]],
        "provided_contract": contract,
    }


def constant(value):
    return ["i64", value]


def contract(name, value):
    return {
        "op": "put_contract",
        "id": name,
        "typed_signature": SIGNATURE,
        "rules": [{"kind": "ensures", "predicate": f"result == {value}"}],
    }


def call_expression(callee, required):
    return {
        "callee_impl_hash": callee,
        "required_contract_hash": required,
        "arguments": [],
    }


def first_operations(result=42, promised=42):
    c, helper, main, interface = map(local, ("contract", "add", "main", "public"))
    return [
        {"op": "set_version", "version": "1.0.0", "expected_version": None},
        contract("contract", promised),
        implementation("add", constant(result), c),
        implementation("main", call_expression(helper, c), c),
        {"op": "put_interface", "id": "public", "name": "main", "public_contract": c},
        {"op": "bind", "interface": interface, "implementation": main, "expected_implementation": None},
        {"op": "set_entry_point", "implementation": main, "expected_implementation": None},
    ]


def create(client, name):
    return client.call("create_package", {
        "name": name, "language_version": "0.1.0", "profile": "scalar",
    })


def apply_request(workspace_id, expected_revision, key, operations):
    return {
        "workspace_id": workspace_id,
        "expected_revision": expected_revision,
        "idempotency_key": key,
        "operations": operations,
    }


def scope(workspace, revision=None):
    return {
        "workspace_id": workspace["workspace_id"],
        "expected_revision": workspace["revision"] if revision is None else revision,
    }


def second_operations(previous, content_hashes):
    c, helper, main = map(local, ("contract_v2", "add_v2", "main_v2"))
    return [
        {"op": "set_version", "version": "2.0.0", "expected_version": "1.0.0"},
        contract("contract_v2", 43),
        {
            **implementation("add_v2", constant(43), c),
            "previous": previous["add"], "expected_hash": content_hashes["add"],
        },
        {
            **implementation("main_v2", call_expression(helper, c), c),
            "previous": previous["main"], "expected_hash": content_hashes["main"],
        },
        {"op": "put_interface", "id": "public_v2", "name": "main", "public_contract": c},
        {
            "op": "bind", "interface": local("public_v2"), "implementation": main,
            "expected_implementation": previous["main"],
        },
        {
            "op": "set_entry_point", "implementation": main,
            "expected_implementation": previous["main"],
        },
    ]


def check_rejected_edits(client, workspace, accepted, request):
    stale = {**request, "idempotency_key": "stale-revision"}
    error = client.call("apply_change_set", stale, succeeds=False)
    assert error["code"] == "StaleRevision", error
    changed_retry = {**request, "operations": first_operations(result=41)}
    error = client.call("apply_change_set", changed_retry, succeeds=False)
    assert error["code"] == "Conflict", error
    cases = {
        "invalid-type": [implementation(
            "wrong-type", ["bool", True], accepted["identities"]["contract"],
        )],
        "missing-callee": [implementation(
            "wrong-callee", call_expression("f" * 64, accepted["identities"]["contract"]),
            accepted["identities"]["contract"],
        )],
        "missing-dependency": [{
            "op": "pin_dependency", "name": "unavailable", "snapshot_id": "e" * 64,
            "expected_snapshot_id": None,
        }],
        "stale-hash": [{
            "op": "remove_object", "table": "functions", "identity": accepted["identities"]["add"],
            "expected_hash": "f" * 64,
        }],
    }
    for label, operations in cases.items():
        args = apply_request(workspace["workspace_id"], accepted["revision"], label, operations)
        client.call("apply_change_set", args, succeeds=False)
        view = client.call("inspect_workspace", {"workspace_id": workspace["workspace_id"]})
        assert view["revision"] == accepted["revision"], (label, view)


def check_scalar_builtin_access(client):
    failure = {
        **implementation("failure", constant(0), local("contract")),
        "canonical_body": [["if", ["bool", True], [["fail", "DivisionByZero"]],
                            [["return", constant(0)]]]],
    }
    declared_error = {
        **contract("contract", 0),
        "rules": [{"kind": "error_declaration", "error_label": "DivisionByZero"}],
    }
    operations = [declared_error, failure]
    for package in ("stdlib.extra", "stdlib"):
        workspace = create(client, package)
        request = apply_request(workspace["workspace_id"], workspace["revision"],
                                "builtin-access", operations)
        allowed = package == "stdlib"
        result = client.call("apply_change_set", request, succeeds=allowed)
        if allowed:
            assert "failure" in result["identities"], result
        else:
            assert result["code"] == "ValidationFailed", result
            assert result["message"] == (
                "builtin__fail may only be used in package stdlib (found in package stdlib.extra)"
            ), result
            current = client.call("inspect_workspace", {"workspace_id": workspace["workspace_id"]})
            assert current["revision"] == workspace["revision"], current


def read_object(client, uri):
    result = client.request("resources/read", uri=uri)
    assert result["contents"][0]["uri"] == uri, result
    return json.loads(result["contents"][0]["text"])


def exercise(executable, root, python):
    state = root / "author"
    with server(executable, state, python) as client:
        tools = {tool["name"]: tool for tool in client.request("tools/list")["tools"]}
        names = {
            "create_package", "open_workspace", "inspect_workspace", "apply_change_set",
            "verify_workspace", "commit_workspace", "build_package", "import_package",
        }
        assert names == set(tools), tools
        for tool in tools.values():
            assert tool["inputSchema"]["type"] == "object", tool
            assert tool["outputSchema"]["type"] == "object", tool
        check_scalar_builtin_access(client)
        workspace = create(client, "demo")
        args = apply_request(workspace["workspace_id"], workspace["revision"], "first", first_operations())
        applied = client.call("apply_change_set", args)
        assert applied["revision"] == workspace["revision"] + 1, applied
        check_rejected_edits(client, workspace, applied, args)
        identities = applied["identities"]
        stored = json.loads((state / "state.json").read_bytes())
        assert stored["workspaces"] == {} and stored["snapshots"] == {}, stored
        workspace_uri = f"llmlang://workspace/{workspace['workspace_id']}"
        main = read_object(client, f"{workspace_uri}/object/functions/{identities['main']}")
        helper = read_object(client, f"{workspace_uri}/object/functions/{identities['add']}")
        assert any(link["uri"].endswith(f"/functions/{identities['add']}") for link in main["outgoing"]), main
        assert any(link["uri"].endswith(f"/functions/{identities['main']}") for link in helper["incoming"]), helper
        content_hashes = {"add": helper["content_hash"], "main": main["content_hash"]}

        assert client.call("apply_change_set", args) == applied
        verified = client.call("verify_workspace", scope(workspace, applied["revision"]))
        assert verified["report"]["ok"], verified
        error = client.call("commit_workspace", scope(workspace, applied["revision"]), succeeds=False)
        assert error["code"] == "UnsupportedProfile", error

        bad = create(client, "incorrect")
        bad_version = client.call("apply_change_set", apply_request(
            bad["workspace_id"], bad["revision"], "bad", first_operations(result=41),
        ))
        rejected = client.call("verify_workspace", scope(bad, bad_version["revision"]))
        assert not rejected["report"]["ok"], rejected

        second = client.call("apply_change_set", apply_request(
            workspace["workspace_id"], applied["revision"], "second", second_operations(identities, content_hashes),
        ))
        assert second["identities"]["add_v2"] != identities["add"], second
        new_main = read_object(client, f"{workspace_uri}/object/functions/{second['identities']['main_v2']}")
        assert second["identities"]["add_v2"] in json.dumps(new_main), new_main
        assert not list((state / "packages").iterdir())
        assert not (state / "pending-package").exists()
        stored = json.loads((state / "state.json").read_bytes())
        assert stored["workspaces"] == {} and stored["snapshots"] == {}, stored

    with server(executable, state, python) as client:
        error = client.call(
            "inspect_workspace", {"workspace_id": workspace["workspace_id"]}, succeeds=False,
        )
        assert error["code"] == "MissingReference", error

    print("MCP scalar editing, verification, and non-persistence checks passed")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--python", default="python3")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="llmlang-mcp-e2e-") as directory:
        exercise(args.executable.resolve(), Path(directory), args.python)


if __name__ == "__main__":
    main()
