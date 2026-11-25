"""Emit versioned LSP repairs in negotiated and deliberately fixed coordinate units."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

TRANSPORT = Path(__file__).resolve().parent.parent / "WIRE-DIAGNOSTIC-01" / "server.py"
spec = spec_from_file_location("frames", TRANSPORT)
frames = module_from_spec(spec)
spec.loader.exec_module(frames)


def units(text, encoding):
    if encoding == "utf-8":
        return len(text.encode("utf-8"))
    if encoding == "utf-16":
        return len(text.encode("utf-16-le")) // 2
    assert encoding == "utf-32"
    return len(text)


def edit_for(uri, document, token, replacement, encoding, scenario):
    version, text = document["version"], document["text"]
    offset = text.rindex(token) if scenario == "wrong-occurrence" else text.index(token)
    prefix = text[:offset]
    line = prefix.count("\n")
    column = units(prefix.rsplit("\n", 1)[-1], encoding)
    length = units(token, encoding)
    if scenario == "malformed-unit":
        column = 1
    item = {"range": {"start": {"line": line, "character": column},
                      "end": {"line": line, "character": column + length}}, "newText": replacement}
    return {"textDocument": {"uri": uri, "version": version}, "edits": [item]}


def serve(policy, scenario):
    documents = {}
    encoding = None
    edit = None
    pending = None
    while message := frames.read_frame():
        method = message.get("method")
        request = message.get("id")
        parameters = message.get("params")
        if method == "initialize":
            requested = parameters["capabilities"].get("general", {}).get("positionEncodings")
            encoding = requested[0] if requested else "utf-16"
            assert encoding in {"utf-8", "utf-16", "utf-32"}
            capabilities = {"textDocumentSync": 1, "codeActionProvider": True}
            if requested:
                capabilities["positionEncoding"] = encoding
            frames.send_frame(id=request, result={"capabilities": capabilities})
        elif method == "textDocument/didOpen":
            item = parameters["textDocument"]
            documents[item["uri"]] = item
        elif method == "textDocument/didChange":
            uri = parameters["textDocument"]["uri"]
            documents[uri] = {**documents[uri], "version": parameters["textDocument"]["version"],
                              "text": parameters["contentChanges"][0]["text"]}
        elif method == "textDocument/codeAction":
            primary = parameters["textDocument"]["uri"]
            companion, = set(documents) - {primary}
            output_encoding = {"negotiated": encoding, "codepoint": "utf-32", "fixed16": "utf-16"}[policy]
            edit = {"documentChanges": [
                edit_for(primary, documents[primary], "bad", "good", output_encoding, scenario),
                edit_for(companion, documents[companion], "old", "new", output_encoding, "ordinary"),
            ]}
            frames.send_frame(id=request, result=[{
                "title": "Repair checked occurrence", "kind": "quickfix",
                "command": {"title": "Apply repair", "command": "rt17.apply"},
            }])
        elif method == "workspace/executeCommand":
            assert edit is not None and pending is None
            pending = request
            frames.send_frame(id="apply", method="workspace/applyEdit", params={"edit": edit})
        elif request == "apply":
            assert pending is not None
            frames.send_frame(id=pending, result=message["result"])
            pending = None
        elif method == "shutdown":
            frames.send_frame(id=request, result=None)
        elif method == "exit":
            return
        elif method != "initialized":
            raise ValueError(message)


if __name__ == "__main__":
    serve(*sys.argv[1:])
