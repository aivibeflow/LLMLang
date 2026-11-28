"""Stable stdio MCP endpoint for a locally managed LLMLang server (Linux)."""

import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import uuid

from mcp_client import DEFAULT_TIMEOUT, RpcError, SUPPORTED_VERSIONS, connect


def object_schema(fields):
    return {"type": "object", "properties": fields, "required": list(fields),
            "additionalProperties": False}


STRING = {"type": "string", "minLength": 1, "maxLength": 128}
UPGRADE_TOOL = {
    "name": "upgrade_server",
    "description": "Install an approved LLMLang release or poll an existing upgrade.",
    "inputSchema": {
        "type": "object",
        "oneOf": [
            object_schema({"version": STRING, "idempotency_key": STRING}),
            object_schema({"operation_id": STRING}),
        ],
    },
    "outputSchema": {"type": "object"},
}


class UpgradeError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def domain(error):
    return {"code": error.code if isinstance(error, UpgradeError) else "UpgradeFailed",
            "message": str(error)}


def tool_result(value, *, is_error=False):
    result = {"content": [{"type": "text", "text": json.dumps(value)}], "isError": is_error}
    if not is_error:
        result["structuredContent"] = value
    return result


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_journal(path, data):
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".journal-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(data, output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp, path)
        sync_directory(path.parent)
    finally:
        Path(temp).unlink(missing_ok=True)


def require_owner(path, *, mode, kind):
    info = path.lstat()
    if info.st_uid != os.geteuid() or info.st_mode & mode or not kind(info.st_mode):
        raise UpgradeError("AccessDenied", f"Invalid type, owner or permissions for {path}")


def prepare_copy(root, candidate):
    for directory, subdirectories, files in os.walk(root):
        for name in subdirectories + files:
            path = Path(directory) / name
            mode = path.lstat().st_mode
            if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                raise UpgradeError("InvalidState", f"Unsupported state entry {path}")
    shutil.copytree(root, candidate)


def sync_tree(root):
    for directory, _, files in os.walk(root, topdown=False):
        for name in files:
            with (Path(directory) / name).open("rb") as file:
                os.fsync(file.fileno())
        sync_directory(directory)


class Supervisor:
    def __init__(self, root, config):
        self.root = root
        self.releases = config["releases"]
        self.control = root.with_name(f".{root.name}.upgrade")
        self.control.mkdir(mode=0o700, exist_ok=True)
        require_owner(self.control, mode=0o077, kind=stat.S_ISDIR)
        self.path = self.control / "journal.json"
        self.lock = threading.Lock()
        self.child = None
        self.connection = None
        self.worker = None
        self.session = "new"
        self.tools = [UPGRADE_TOOL]
        self.scalar_snapshots = set()
        self.scalar_workspaces = set()
        self.edited_scalar = set()
        self.session_lock = (self.control / "lock").open("a")
        try:
            fcntl.flock(self.session_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.journal = (json.loads(self.path.read_text()) if self.path.exists() else
                            {"version": config["initial_version"], "operations": {}, "pending": None})
            self.recover()
            self.start_child(self.journal["version"], self.root)
        except BaseException:
            self.session_lock.close()
            raise

    def command(self, version, root):
        release = self.releases[version]
        binary = Path(release["binary"])
        if not binary.is_absolute():
            raise UpgradeError("InvalidRelease", "The release binary path must be absolute")
        command = [str(binary), "--state-dir", str(root)]
        if "backend" in release:
            backend = Path(release["backend"])
            if not backend.is_absolute():
                raise UpgradeError("InvalidRelease", "The release backend path must be absolute")
            command.extend(["--backend", str(backend)])
        return command

    def start_child(self, version, root):
        context = connect(self.command(version, root), timeout=DEFAULT_TIMEOUT)
        child = context.__enter__()
        try:
            child.request("ping")
            tools = child.request("tools/list")["tools"]
        except BaseException:
            context.__exit__(None, None, None)
            raise
        self.connection = context
        self.child = child
        self.tools = [*[tool for tool in tools if tool["name"] != UPGRADE_TOOL["name"]], UPGRADE_TOOL]

    def stop_child(self):
        context = self.connection
        self.child = self.connection = None
        if context is not None:
            context.__exit__(None, None, None)

    def close(self):
        if self.worker is not None:
            self.worker.join()
        self.stop_child()
        self.session_lock.close()

    def save(self, journal):
        write_journal(self.path, journal)
        self.journal = journal

    def operation_dir(self, identifier):
        return self.control / identifier

    def restore_previous(self, work):
        backup = work / "previous"
        if backup.exists():
            if self.root.exists():
                self.root.rename(work / "rejected")
            backup.rename(self.root)
            sync_directory(self.root.parent)
            sync_directory(work)

    def recover(self):
        pending = self.journal["pending"]
        if pending is not None:
            self.restore_previous(self.operation_dir(pending))
            if not self.root.is_dir():
                raise UpgradeError("RecoveryFailed", "The previous state directory is missing")
            self.finish(pending, "failed", error={
                "code": "UpgradeInterrupted", "message": "Recovered the previous state after interruption",
            })

    def finish(self, identifier, status, *, version=None, **details):
        active = version or self.journal["version"]
        operations = dict(self.journal["operations"])
        operations[identifier] = {**operations[identifier], "status": status,
                                  "version": active, **details}
        self.save({"version": active, "operations": operations, "pending": None})

    def upgrade(self, args):
        if not isinstance(args, dict):
            raise UpgradeError("InvalidArguments", "Expected an argument object")
        if not all(isinstance(item, str) and 0 < len(item) <= 128 for item in args.values()):
            raise UpgradeError("InvalidArguments", "Invalid upgrade argument value")
        with self.lock:
            operations = self.journal["operations"]
            if args.keys() == {"operation_id"}:
                operation = operations.get(args["operation_id"])
                if not operation:
                    raise UpgradeError("MissingReference", "Unknown upgrade operation")
                return self.public_status(operation)
            if args.keys() != {"version", "idempotency_key"}:
                raise UpgradeError("InvalidArguments", "Supply version and idempotency_key or operation_id")
            version, key = args["version"], args["idempotency_key"]
            for operation in operations.values():
                if operation["idempotency_key"] == key:
                    if operation["requested_version"] != version:
                        raise UpgradeError("Conflict", "Upgrade idempotency key already refers to another release")
                    return self.public_status(operation)
            if self.journal["pending"] is not None:
                raise UpgradeError("UpgradeInProgress", "Another upgrade is running")
            current = self.journal["version"]
            if version not in self.releases:
                raise UpgradeError("UnknownRelease", "The release is absent from the approved catalog")
            route = self.releases[current]["state_format"], self.releases[version]["state_format"]
            if version != current and route not in {(6, 7), (7, 7), (6, 8), (7, 8), (8, 8), (6, 9), (7, 9), (8, 9), (9, 9)}:
                raise UpgradeError("UnsupportedUpgrade", "Unsupported server state format transition")
            if version != current and self.edited_scalar:
                raise UpgradeError("UnsavedWork", "An edited in-memory scalar workspace is still open")
            identifier = uuid.uuid4().hex
            record = {"operation_id": identifier, "status": "running", "version": current,
                      "requested_version": version, "idempotency_key": key}
            self.save({**self.journal, "pending": identifier,
                       "operations": {**operations, identifier: record}})
            if version == current:
                self.finish(identifier, "succeeded", snapshot_ids={})
                return self.public_status(self.journal["operations"][identifier])
            self.worker = threading.Thread(target=self.run_upgrade, args=(identifier, version, route))
            self.worker.start()
            return self.public_status(record)

    @staticmethod
    def public_status(operation):
        return {k: v for k, v in operation.items() if k != "idempotency_key"}

    def run_upgrade(self, identifier, version, route):
        work = self.operation_dir(identifier)
        candidate = work / "candidate"
        try:
            work.mkdir(mode=0o700)
            self.stop_child()
            require_owner(self.root, mode=0o077, kind=stat.S_ISDIR)
            with (self.root / "lock").open("r+b") as state_lock:
                fcntl.flock(state_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                prepare_copy(self.root, candidate)
                result = self.prepare_release(version, candidate, route)
                sync_tree(candidate)
                self.root.rename(work / "previous")
                sync_directory(self.root.parent)
                sync_directory(work)
                candidate.rename(self.root)
                sync_directory(self.root.parent)
                sync_directory(work)
                self.start_child(version, self.root)
                with self.lock:
                    self.finish(identifier, "succeeded", version=version,
                                snapshot_ids=result["snapshot_ids"],
                                smoke_snapshot_id=result.get("smoke_snapshot_id"),
                                backup_path=str(work / "previous"))
                    self.scalar_snapshots.clear()
                    self.scalar_workspaces.clear()
        except Exception as error:
            self.stop_child()
            try:
                self.restore_previous(work)
                if not self.root.is_dir():
                    raise UpgradeError("RecoveryFailed", "The previous state directory is missing")
                self.start_child(self.journal["version"], self.root)
            except Exception as recovery:
                error = UpgradeError("RecoveryFailed", f"{error}. Previous server unavailable: {recovery}")
                with self.lock:
                    operations = self.journal["operations"]
                    failed = {**operations[identifier], "status": "failed", "error": domain(error)}
                    self.save({**self.journal, "operations": {**operations, identifier: failed}})
                return
            with self.lock:
                self.finish(identifier, "failed", error=domain(error))

    def prepare_release(self, version, candidate, route):
        command = self.command(version, candidate)
        if route[0] != route[1]:
            migration = subprocess.run([*command, f"--migrate-v{route[0]}-copy"], stdin=subprocess.DEVNULL,
                                       capture_output=True, text=True, timeout=DEFAULT_TIMEOUT)
            if migration.returncode:
                raise UpgradeError("MigrationFailed", migration.stderr.strip() or "State conversion failed")
            result = json.loads(migration.stdout)
        else:
            state_path = candidate / "state.json"
            state = json.loads(state_path.read_text()) if state_path.exists() else {}
            result = {"snapshot_ids": {key: key for key in state.get("snapshots", {})}}
        with connect(command) as child:
            child.request("ping")
            child.request("tools/list")
            if snapshot := result.get("smoke_snapshot_id"):
                reply = child.call_tool("build_package", {"snapshot_id": snapshot, "target": "linux-x86_64"})
                if reply.get("isError"):
                    raise UpgradeError("SmokeBuildFailed", reply["content"][0]["text"])
                if not Path(reply["structuredContent"]["artifact"]).is_file():
                    raise UpgradeError("SmokeBuildFailed", "The smoke build did not create an artifact")
        return result

    def track_workspaces(self, method, params, result):
        if (method != "tools/call" or result.get("isError")
                or self.releases[self.journal["version"]]["state_format"] >= 9):
            return
        name = params.get("name")
        value = result.get("structuredContent", {})
        if name == "create_package":
            self.scalar_snapshots.add(value["base_snapshot"])
            self.scalar_workspaces.add(value["workspace_id"])
        if name == "open_workspace" and value["base_snapshot"] in self.scalar_snapshots:
            self.scalar_workspaces.add(value["workspace_id"])
        if name == "apply_change_set" and value["workspace_id"] in self.scalar_workspaces:
            self.edited_scalar.add(value["workspace_id"])

    def dispatch(self, method, params):
        if method == "ping":
            return {}
        if method == "initialize" and self.session == "new":
            self.session = "initializing"
            requested = params.get("protocolVersion")
            result = {
                "protocolVersion": requested if requested in SUPPORTED_VERSIONS else SUPPORTED_VERSIONS[0],
                "serverInfo": {"name": "llmlang-supervisor", "version": self.journal["version"]},
                "capabilities": {"tools": {}, "resources": {}},
            }
            if self.child is not None and "instructions" in self.child.server:
                result["instructions"] = self.child.server["instructions"]
            return result
        if self.session != "ready":
            raise RpcError({"code": -32600, "message": "Initialization required"})
        if method == "tools/list":
            return {"tools": self.tools}
        if method == "tools/call" and params.get("name") == "upgrade_server":
            try:
                return tool_result(self.upgrade(params.get("arguments", {})))
            except UpgradeError as error:
                return tool_result(domain(error), is_error=True)
        with self.lock:
            pending = self.journal["pending"]
            child = self.child
        if pending or child is None:
            error = UpgradeError("UpgradeInProgress" if pending else "ServerUnavailable",
                                 "The package server is temporarily unavailable")
            if method == "tools/call":
                return tool_result(domain(error), is_error=True)
            raise RpcError({"code": -32000, "message": str(error), "data": domain(error)})
        result = child.request(method, **params)
        self.track_workspaces(method, params, result)
        return result

    def handle(self, line):
        def response(request_id, **fields):
            return {"jsonrpc": "2.0", "id": request_id, **fields}

        try:
            request = json.loads(line)
        except ValueError:
            return response(None, error={"code": -32700, "message": "Parse error"})
        if (not isinstance(request, dict) or request.get("jsonrpc") != "2.0"
                or not isinstance(request.get("method"), str)):
            return response(None, error={"code": -32600, "message": "Invalid request"})
        method = request["method"]
        if "id" not in request:
            if method == "notifications/initialized" and self.session == "initializing":
                self.session = "ready"
            return None
        identifier = request["id"]
        params = request.get("params", {})
        if not isinstance(params, dict):
            return response(identifier, error={"code": -32602, "message": "Invalid params"})
        try:
            return response(identifier, result=self.dispatch(method, params))
        except RpcError as error:
            return response(identifier, error=error.error)
        except (OSError, EOFError, ValueError) as error:
            return response(identifier, error={"code": -32603, "message": str(error)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--releases", type=Path, required=True)
    args = parser.parse_args()
    try:
        require_owner(args.releases, mode=0o022, kind=stat.S_ISREG)
        config = json.loads(args.releases.read_text())
        supervisor = Supervisor(args.state_dir.resolve(), config)
        try:
            for line in sys.stdin:
                reply = supervisor.handle(line)
                if reply is not None:
                    print(json.dumps(reply), flush=True)
        finally:
            supervisor.close()
    except (OSError, ValueError, KeyError, RuntimeError, EOFError) as error:
        print(f"llmlang-supervisor: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
