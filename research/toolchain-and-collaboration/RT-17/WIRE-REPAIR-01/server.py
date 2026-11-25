"""Fixture LSP code action and workspace edit server."""
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys

PREVIOUS = Path(__file__).resolve().parent.parent / "WIRE-DIAGNOSTIC-01" / "server.py"
dependency = spec_from_file_location("diagnostic_frames", PREVIOUS)
frames = module_from_spec(dependency)
dependency.loader.exec_module(frames)
read_frame, send_frame = frames.read_frame, frames.send_frame


class Server:
    def __init__(self, directory, policy, wrong_repair):
        self.directory = directory
        self.policy = policy
        self.wrong_repair = wrong_repair
        self.documents = {}
        self.action = None
        self.waiting_for_apply = None

    def read_scope(self):
        paths = ("provider", "notes") if self.policy == "workspace" else ("provider",)
        return [self.directory.joinpath(path).read_text(encoding="utf-8") for path in paths]

    def create_action(self):
        self.action = {"scope": self.read_scope(), "documents": dict(self.documents),
                       "limit": 99 if self.wrong_repair else 5}
        return [{"title": "Repair bounded policy", "kind": "quickfix",
                 "command": {"title": "Apply bounded policy repair", "command": "rt17.apply", "arguments": [1]}}]

    def edit(self):
        documents = []
        original = self.action["documents"]
        replacements = {
            (self.directory / "rule").as_uri(): {"limit": self.action["limit"]},
            (self.directory / "config").as_uri(): {"mode": "strict"},
        }
        for uri, content in replacements.items():
            version, text = original[uri]
            item = {"range": {"start": {"line": 0, "character": 0},
                              "end": {"line": 0, "character": len(text)}},
                    "newText": json.dumps(content, separators=(",", ":"))}
            documents.append({"textDocument": {"uri": uri, "version": version}, "edits": [item]})
        if self.policy == "legacy":
            return {"changes": {item["textDocument"]["uri"]: item["edits"] for item in documents}}
        return {"documentChanges": documents}

    def start_apply(self, request):
        scope_checked = self.policy in {"preflight", "workspace", "commit-bound"}
        current = self.read_scope()
        if scope_checked and current != self.action["scope"]:
            return {"stage": "server", "reason": "stale-scope"}
        if scope_checked and self.action["limit"] != int(current[0]):
            return {"stage": "server", "reason": "behavior-mismatch"}
        self.waiting_for_apply = request
        send_frame(id="apply", method="workspace/applyEdit", params={"label": "Fixture repair", "edit": self.edit()})
        return None

    def dispatch(self, message):
        method = message.get("method")
        params = message.get("params", {})
        if method is None:
            assert message["id"] == "apply" and self.waiting_for_apply is not None
            send_frame(id=self.waiting_for_apply, result={"stage": "client", **message["result"]})
            self.waiting_for_apply = None
            return
        result = None
        if method == "initialize":
            apply = params["capabilities"]["workspace"]["workspaceEdit"]
            assert apply["documentChanges"] and apply["failureHandling"] == "transactional"
            result = {"capabilities": {"textDocumentSync": {"openClose": True, "change": 1},
                                      "codeActionProvider": True,
                                      "executeCommandProvider": {"commands": ["rt17.apply"]}}}
        elif method == "textDocument/didOpen":
            document = params["textDocument"]
            self.documents[document["uri"]] = document["version"], document["text"]
        elif method == "textDocument/didChange":
            document = params["textDocument"]
            self.documents[document["uri"]] = document["version"], params["contentChanges"][0]["text"]
        elif method == "textDocument/codeAction":
            result = self.create_action()
        elif method == "workspace/executeCommand":
            assert params["command"] == "rt17.apply" and params["arguments"] == [1]
            result = self.start_apply(message["id"])
            if result is None:
                return
        elif method not in {"initialized", "shutdown"}:
            raise ValueError(f"unexpected LSP method {method}")
        if "id" in message:
            send_frame(id=message["id"], result=result)


if __name__ == "__main__":
    server = Server(Path(sys.argv[1]), sys.argv[2], sys.argv[3] == "wrong-repair")
    while (message := read_frame()) is not None and message.get("method") != "exit":
        server.dispatch(message)
