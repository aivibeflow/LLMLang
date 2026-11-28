"""Upgrade a live MCP session from a real v6 server and verify rollback."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time

DRAFT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(DRAFT / "server"))

from mcp_client import connect


def call(client, name, args, *, error=None):
    reply = client.call_tool(name, args)
    if error:
        assert reply["isError"] and json.loads(reply["content"][0]["text"])["code"] == error, reply
        return
    assert not reply["isError"], reply
    return reply["structuredContent"]


def finished(client, operation):
    timeout = time.monotonic() + 180
    while operation["status"] == "running":
        assert time.monotonic() < timeout, operation
        time.sleep(0.05)
        operation = call(client, "upgrade_server", {"operation_id": operation["operation_id"]})
    return operation


def snapshot_id(program):
    encoded = json.dumps(["llmlang-server-snapshot/v1", program],
                         ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def exercise(old, new, fixtures, directory):
    state = directory / "state"
    with connect([str(old), "--state-dir", str(state)]) as client:
        builtin = call(client, "import_package", {"path": str(fixtures / "builtin")})["snapshot_id"]
        hello_path = fixtures / "examples/0001-hello-world"
        hello = call(client, "import_package", {"path": str(hello_path)})["snapshot_id"]

    # Simulate a managed package and use an exact dependency pin in the imported snapshot.
    managed = state / "packages/builtin/0.1.0"
    shutil.copytree(fixtures / "builtin", managed)
    state_file = state / "state.json"
    catalog = json.loads(state_file.read_text())
    program = catalog["snapshots"].pop(hello)
    assert snapshot_id(program) == hello
    program["manifest"]["dependencies"]["builtin"] = builtin
    hello = snapshot_id(program)
    catalog["snapshots"][hello] = program
    old_catalog = json.dumps(catalog)
    state_file.write_text(old_catalog)

    # This release passes migration and the staging smoke check but fails at the live path.
    failing = directory / "failing-release"
    failing.write_text(
        f"#!{sys.executable}\n"
        "import os, sys\n"
        f"if sys.argv[sys.argv.index('--state-dir') + 1] == {str(state)!r}:\n"
        "    sys.exit(1)\n"
        f"os.execv({str(new)!r}, [{str(new)!r}, *sys.argv[1:]])\n"
    )
    failing.chmod(0o700)
    releases = directory / "releases.json"
    releases.write_text(json.dumps({
        "initial_version": "v6",
        "releases": {
            "v6": {"binary": str(old), "state_format": 6},
            "bad": {"binary": str(failing), "state_format": 7},
            "v7": {"binary": str(new), "state_format": 7},
            "v7-next": {"binary": str(new), "state_format": 7},
        },
    }))
    command = [sys.executable, "-B", str(DRAFT / "server/mcp_supervisor.py"),
               "--state-dir", str(state), "--releases", str(releases)]
    with connect(command) as client:
        assert "upgrade_server" in {tool["name"] for tool in client.request("tools/list")["tools"]}
        call(client, "upgrade_server", {"version": "unknown", "idempotency_key": "unknown"},
             error="UnknownRelease")
        bad = call(client, "upgrade_server", {"version": "bad", "idempotency_key": "bad"})
        assert bad["status"] == "running"
        bad = finished(client, bad)
        assert bad["status"] == "failed" and bad["version"] == "v6", bad
        assert state_file.read_text() == old_catalog
        assert (managed / "manifest.json").read_text().find("tables.v6") >= 0
        call(client, "build_package", {"snapshot_id": hello, "target": "linux-x86_64"})

        request = {"version": "v7", "idempotency_key": "v7"}
        operation = call(client, "upgrade_server", request)
        assert operation["status"] == "running"
        repeated = call(client, "upgrade_server", request)
        assert repeated["operation_id"] == operation["operation_id"]
        operation = finished(client, operation)
        assert operation["status"] == "succeeded" and operation["version"] == "v7", operation
        bootstrap = "llmlang://doc/bootstrap.md"
        assert any(item["uri"] == bootstrap for item in client.request("resources/list")["resources"])
        assert client.request("resources/read", uri=bootstrap)["contents"][0]["mimeType"] == "text/markdown"
        mapped = operation["snapshot_ids"]
        assert set(mapped) == {hello, builtin} and all(a != b for a, b in mapped.items())
        assert operation["smoke_snapshot_id"] == mapped[hello], operation
        assert (Path(operation["backup_path"]) / "state.json").read_text() == old_catalog
        assert json.loads((managed / "manifest.json").read_text())["profile"] == "llmlang.spg.tables.v7"
        assert json.loads((managed / "package.json").read_text())["snapshot_id"] == mapped[builtin]
        assert (managed / "README.md").read_bytes() == (fixtures / "builtin/README.md").read_bytes()
        assert json.loads(state_file.read_text())["snapshots"][mapped[hello]]["manifest"]["dependencies"]["builtin"] == mapped[builtin]
        output = call(client, "build_package", {"snapshot_id": mapped[hello], "target": "linux-x86_64"})
        assert Path(output["artifact"]).is_file()
        workspace = call(client, "create_package", {
            "name": "unsaved", "profile": "scalar", "language_version": "0.1.0",
        })
        call(client, "apply_change_set", {
            "workspace_id": workspace["workspace_id"], "expected_revision": 0,
            "idempotency_key": "edit", "operations": [
                {"op": "set_version", "version": "1", "expected_version": None},
            ],
        })
        call(client, "upgrade_server", {"version": "v7-next", "idempotency_key": "next"},
             error="UnsavedWork")
    with connect(command) as client:
        assert client.server["serverInfo"]["version"] == "v7"
        assert "llmlang://doc/bootstrap.md" in client.server["instructions"]
        assert call(client, "upgrade_server", request) == operation

    # Recreate a crash after the old directory was moved and before the new one was activated.
    management = directory / ".state.upgrade"
    journal = management / "journal.json"
    interrupted = "interrupted"
    record = json.loads(journal.read_text())
    record["pending"] = interrupted
    record["operations"][interrupted] = {
        "operation_id": interrupted, "requested_version": "v7-next", "version": "v7",
        "idempotency_key": interrupted, "status": "running",
    }
    journal.write_text(json.dumps(record))
    scratch = management / interrupted
    scratch.mkdir()
    state.rename(scratch / "previous")
    with connect(command) as client:
        recovered = call(client, "upgrade_server", {"operation_id": interrupted})
        assert recovered["status"] == "failed" and recovered["error"]["code"] == "UpgradeInterrupted"
        call(client, "build_package", {"snapshot_id": mapped[hello], "target": "linux-x86_64"})
        next_release = call(client, "upgrade_server", {"version": "v7-next", "idempotency_key": "next"})
        next_release = finished(client, next_release)
        assert next_release["status"] == "succeeded" and next_release["version"] == "v7-next"
        assert next_release["snapshot_ids"] == {identifier: identifier for identifier in mapped.values()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("v6", type=Path)
    parser.add_argument("v7", type=Path)
    parser.add_argument("v6_draft", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="llmlang-upgrade-e2e-") as directory:
        exercise(args.v6.resolve(), args.v7.resolve(), args.v6_draft.resolve(), Path(directory))
    print("MCP upgrade, snapshot mapping, rollback, and interruption recovery passed")


if __name__ == "__main__":
    main()
