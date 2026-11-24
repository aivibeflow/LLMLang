"""Bounded RT-19 MCP stdio adapter over the existing workspace prototype."""
from dataclasses import asdict
import json
import math
from pathlib import Path
import re
import sys
from urllib.parse import quote, unquote

from jsonschema import Draft202012Validator, ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "PROTOTYPES" / "TOOLCHAIN-SERVER-01"))
from toolchain import Change, Entity, InMemoryToolchain, ToolchainError


VERSION = "2025-11-25"
ID = "module/math+basis"
CONFIG = "module/config"
TEMPLATE = "llmlang://snapshot/{snapshot_id}/entity/{stable_id}"
DIGEST = {"type": "string", "pattern": r"^sha256:[0-9a-f]{64}$"}
WORKSPACE = {"type": "string", "pattern": r"^ws-[0-9a-f]{24}$"}
REVISION = {"type": "integer", "minimum": 0}
STRING = {"type": "string", "minLength": 1}

def record(**fields):
    return {"type": "object", "properties": fields, "required": list(fields),
            "additionalProperties": False}

def choice(value):
    return {"const": value}

def render(value):
    return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":"))

ENTITY_FIELDS = {"stable_id": STRING, "kind": STRING, "payload": {"type": "object"}}
ENTITY = record(**ENTITY_FIELDS, content_hash=DIGEST)
CHANGE = {"oneOf": [
    record(action=choice("add"), **ENTITY_FIELDS, expected_hash={"type": "null"}),
    record(action=choice("update"), **ENTITY_FIELDS, expected_hash=DIGEST),
    record(action=choice("remove"), stable_id=STRING, expected_hash=DIGEST),
]}
VIEW = record(workspace_id=WORKSPACE, base_snapshot=DIGEST, working_snapshot=DIGEST,
              revision=REVISION, state={"enum": ["open", "accepted", "discarded"]})
MUTATION = {"workspace_id": WORKSPACE, "expected_revision": REVISION}
PROMPT = record(workspace_id=WORKSPACE, snapshot_id=DIGEST)
TOOLS = {
    name: {"name": name, "description": description, "inputSchema": inputs, "outputSchema": VIEW}
    for name, description, inputs in [
        ("open_workspace", "Open an isolated workspace at an explicit snapshot.",
         record(snapshot_id=DIGEST)),
        ("inspect_workspace", "Read the workspace revision and snapshot IDs.",
         record(workspace_id=WORKSPACE)),
        ("apply_change_set", "Atomically apply changes against one workspace revision.",
         record(**MUTATION, changeset_id=STRING,
                changes={"type": "array", "minItems": 1, "items": CHANGE})),
        ("accept_workspace", "Accept the current immutable snapshot at an explicit revision.",
         record(**MUTATION)),
    ]
}

class ProtocolError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def entity_uri(snapshot_id, stable_id):
    return TEMPLATE.format(snapshot_id=snapshot_id, stable_id=quote(stable_id, safe=""))


def tool_result(value, *, error=False):
    result = {"content": [{"type": "text", "text": render(value)}], "isError": error}
    if not error:
        result["structuredContent"] = value
    return result


class Adapter:
    def __init__(self):
        self.domain = InMemoryToolchain()
        self.seed = self.domain.create_snapshot([
            Entity(ID, "module", {"value": 1, "refs": [CONFIG]}),
            Entity(CONFIG, "module", {"value": 10}),
        ])
        self.initialized = False
        self.ready = False

    def call_tool(self, params):
        Draft202012Validator(record(name=STRING, arguments={"type": "object"})).validate(params)
        name = params["name"]
        if name not in TOOLS:
            raise ProtocolError(-32602, "Unknown tool")
        args = params["arguments"]
        try:
            Draft202012Validator(TOOLS[name]["inputSchema"]).validate(args)
            if name == "open_workspace":
                return tool_result(asdict(self.domain.open_workspace(args["snapshot_id"])))
            workspace_id = args["workspace_id"]
            if name == "apply_change_set":
                change_set = self.domain.propose(
                    workspace_id, args["expected_revision"],
                    [Change(**change) for change in args["changes"]], args["changeset_id"],
                )
                self.domain.apply(change_set, args["expected_revision"])
            elif name == "accept_workspace":
                self.domain.accept(workspace_id, args["expected_revision"])
            return tool_result(asdict(self.domain.get_workspace(workspace_id)))
        except ValidationError:
            return tool_result({"code": "InvalidArguments"}, error=True)
        except ToolchainError as error:
            return tool_result({"code": type(error).__name__}, error=True)
        except ValueError:
            return tool_result({"code": "InvalidArguments"}, error=True)

    def read_resource(self, params):
        Draft202012Validator(record(uri=STRING)).validate(params)
        uri = params["uri"]
        match = re.fullmatch(r"llmlang://snapshot/(sha256:[0-9a-f]{64})/entity/([^/]+)", uri)
        if not match:
            raise ProtocolError(-32602, "Invalid snapshot entity URI")
        snapshot, encoded_id = match.groups()
        stable_id = unquote(encoded_id)
        if uri != entity_uri(snapshot, stable_id):
            raise ProtocolError(-32602, "Invalid snapshot entity encoding")
        try:
            entity = self.domain.get_entity(snapshot, stable_id)
        except ToolchainError as error:
            raise ProtocolError(-32002, "Snapshot entity not found") from error
        value = {"stable_id": entity.stable_id, "kind": entity.kind,
                 "payload": entity.payload, "content_hash": entity.content_hash}
        Draft202012Validator(ENTITY).validate(value)
        return {"contents": [{"uri": uri, "mimeType": "application/json", "text": render(value)}]}

    def get_prompt(self, params):
        Draft202012Validator(record(name=choice("plan_change"), arguments=PROMPT)).validate(params)
        args = params["arguments"]
        try:
            view = self.domain.get_workspace(args["workspace_id"])
        except ToolchainError as error:
            raise ProtocolError(-32602, "Unknown workspace for prompt") from error
        if view.working_snapshot != args["snapshot_id"]:
            raise ProtocolError(-32602, "Snapshot does not match the workspace")
        text = "Plan a change against this explicit workspace, snapshot and revision. " + render({
            **args, "revision": view.revision,
        })
        return {"messages": [{"role": "user", "content": {"type": "text", "text": text}}]}

    def dispatch(self, method, params):
        if method == "initialize":
            if self.initialized:
                raise ProtocolError(-32600, "Already initialized")
            if not isinstance(params, dict) or not isinstance(params.get("protocolVersion"), str):
                raise ProtocolError(-32602, "Protocol version required")
            self.initialized = True
            return {"protocolVersion": VERSION, "serverInfo": {"name": "llmlang-rt19", "version": "0.1"},
                    "capabilities": {"tools": {}, "resources": {}, "prompts": {}}}
        if method == "notifications/initialized" and self.initialized:
            self.ready = True
            return None
        if method == "ping":
            return {}
        if not self.ready:
            raise ProtocolError(-32600, "Initialization required")
        if method == "tools/list":
            return {"tools": list(TOOLS.values())}
        if method == "tools/call":
            return self.call_tool(params)
        if method == "resources/list":
            return {"resources": [
                {"name": "fixture-" + name, "uri": entity_uri(self.seed, stable_id),
                 "mimeType": "application/json"}
                for name, stable_id in (("module", ID), ("config", CONFIG))
            ]}
        if method == "resources/templates/list":
            return {"resourceTemplates": [{"name": "snapshot_entity",
                                          "uriTemplate": TEMPLATE, "mimeType": "application/json"}]}
        if method == "resources/read":
            return self.read_resource(params)
        if method == "prompts/list":
            return {"prompts": [{"name": "plan_change", "arguments": [
                {"name": name, "required": True} for name in PROMPT["required"]
            ]}]}
        if method == "prompts/get":
            return self.get_prompt(params)
        raise ProtocolError(-32601, "Method not found")


def reject_constant(value):
    raise ValueError(f"Invalid JSON constant: {value}")


def finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Non-finite JSON number")
    return number


def serve():
    adapter = Adapter()
    for line in sys.stdin:
        request_id = None
        notification = False
        try:
            request = json.loads(line, parse_constant=reject_constant, parse_float=finite_float)
            if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
                raise ProtocolError(-32600, "Invalid request")
            request_id = request.get("id")
            method = request.get("method")
            if not isinstance(method, str):
                raise ProtocolError(-32600, "Invalid method")
            notification = "id" not in request
            result = adapter.dispatch(method, request.get("params", {}))
            response = {"result": result}
        except ValueError as error:
            if isinstance(error, json.JSONDecodeError):
                response = {"error": {"code": -32700, "message": "Parse error"}}
            else:
                response = {"error": {"code": -32602, "message": "Invalid params"}}
        except ValidationError:
            response = {"error": {"code": -32602, "message": "Invalid params"}}
        except ProtocolError as error:
            response = {"error": {"code": error.code, "message": str(error)}}
        if not notification:
            print(render({"jsonrpc": "2.0", "id": request_id, **response}), flush=True)


if __name__ == "__main__":
    serve()
