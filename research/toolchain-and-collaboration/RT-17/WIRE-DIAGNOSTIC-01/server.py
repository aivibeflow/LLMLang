"""Small LSP server with deterministic worker completion for the RT-17 fixture."""
import hashlib
import json
from pathlib import Path
import sys

FIXTURE = Path(__file__).resolve().parents[2] / "PROTOTYPES" / "DIAGNOSTIC-REPLAY-01"
sys.path.insert(0, str(FIXTURE))

from test_diagnostic_publication import BASE, ENTRY, OVERRIDE, evaluate, key


def read_frame():
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line == b"\r\n":
            break
        name, value = line.split(b":", 1)
        headers[name.lower()] = value.strip()
    payload = sys.stdin.buffer.read(int(headers[b"content-length"]))
    return json.loads(payload)


def send_frame(**message):
    payload = json.dumps({"jsonrpc": "2.0", **message}, separators=(",", ":")).encode()
    sys.stdout.buffer.write(f"Content-Length: {len(payload)}\r\n\r\n".encode())
    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()


def diagnostics(files):
    return [{"code": code, "message": messages[code], "severity": 1, "source": "rt17-fixture",
             "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 4}}}
            for code in evaluate(files)]


messages = {"TYPE": "Selected provider does not meet the configured entry type",
            "PARSE": "Expected the fixture call expression"}


class Server:
    def __init__(self, directory, policy):
        self.directory = directory
        self.policy = policy
        self.uri = (directory / ENTRY).as_uri()
        self.files = {}
        self.text = b""
        self.version = None
        self.refresh_id = 0
        self.pull_refresh = False
        self.capture = None

    def read_dependencies(self):
        files = {ENTRY: self.text}
        for name in (BASE.keys() | {OVERRIDE}) - {ENTRY}:
            path = self.directory / name
            if path.is_file():
                files[name] = path.read_bytes()
        return files

    def identity(self):
        return self.version, key(self.files, self.policy)

    def refresh(self, previous):
        self.files = self.read_dependencies()
        if previous != self.identity() and self.pull_refresh:
            self.refresh_id += 1
            send_frame(id=f"refresh-{self.refresh_id}", method="workspace/diagnostic/refresh")

    def document(self, params):
        document = params["textDocument"]
        if document["uri"] != self.uri:
            raise ValueError("unknown document")
        return document

    def dispatch(self, method, params):
        if method == "initialize":
            self.pull_refresh = params["capabilities"]["workspace"]["diagnostics"]["refreshSupport"]
            return {"capabilities": {"textDocumentSync": {"openClose": True, "change": 1},
                                     "diagnosticProvider": {"interFileDependencies": True,
                                                            "workspaceDiagnostics": False}}}
        if method == "textDocument/didOpen":
            document = self.document(params)
            self.version = document["version"]
            self.text = document["text"].encode()
            self.files = self.read_dependencies()
        elif method == "textDocument/didChange":
            previous = self.identity()
            document = self.document(params)
            self.version = document["version"]
            self.text = params["contentChanges"][0]["text"].encode()
            self.refresh(previous)
        elif method == "workspace/didChangeWatchedFiles":
            self.refresh(self.identity())
        elif method == "textDocument/diagnostic":
            self.document(params)
            result = hashlib.sha256(repr(self.identity()).encode()).hexdigest()
            if params.get("previousResultId") == result:
                return {"kind": "unchanged", "resultId": result}
            return {"kind": "full", "resultId": result, "items": diagnostics(self.files)}
        elif method == "rt17/testCapture":
            self.capture = self.identity(), self.version, diagnostics(self.files)
            return {"version": self.version}
        elif method == "rt17/testFinish":
            observed, version, items = self.capture
            self.capture = None
            published = params["complete"] and observed == self.identity()
            if published:
                send_frame(method="textDocument/publishDiagnostics",
                           params={"uri": self.uri, "version": version, "diagnostics": items})
            return {"published": published}
        elif method not in {"initialized", "shutdown"}:
            raise ValueError(f"unexpected LSP method {method}")
        return None


if __name__ == "__main__":
    server = Server(Path(sys.argv[1]), sys.argv[2])
    while (message := read_frame()) is not None:
        method = message.get("method")
        if method is None:
            continue
        if method == "exit":
            break
        result = server.dispatch(method, message.get("params", {}))
        if "id" in message:
            send_frame(id=message["id"], result=result)
