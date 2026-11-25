"""MCP stdio adapter over the transport-neutral Knowledge Context page reader."""
from dataclasses import replace
import json
from pathlib import Path
import runpy
from secrets import token_urlsafe
import sys

import anyio
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

PAGES = runpy.run_path(str(Path(__file__).resolve().parents[1] / "KNOWLEDGE-CONTEXT-PAGES-01/run.py"))
UNAVAILABLE = PAGES["UNAVAILABLE"]
STRING = {"type": "string", "minLength": 1}
DIGEST = {"type": "string", "pattern": "^[a-f0-9]{64}$"}
TOKEN = {"type": "string", "minLength": 20}


def record(**properties):
    return {"type": "object", "required": list(properties), "properties": properties,
            "additionalProperties": False}


def status(value):
    return {"const": value}


ASSEMBLED = record(status=status("assembled"), manifest_sha256=DIGEST)
REFERENCE = record(source=STRING, sha256=DIGEST)
REFERENCES = {"type": "object", "additionalProperties": REFERENCE}
MANIFEST = record(snapshot=STRING, purpose=STRING, assembly_version=status(1),
                  scope_revision=STRING, budget_utf8_bytes={"type": "integer", "minimum": 0},
                  required=REFERENCES, bindings=REFERENCES,
                  omissions={"type": "object", "additionalProperties": STRING})
INSPECTED = record(status=status("ready"), manifest=MANIFEST,
                   manifest_sha256=DIGEST, first_cursor=TOKEN)
ENTRY = record(role=STRING, reference=REFERENCE, text={"type": "string"})
NULL = {"type": "null"}
PAGE = {"oneOf": [
    record(status=status("page"), entry=ENTRY, next_cursor=TOKEN, rendered_sha256=NULL),
    record(status=status("page"), entry=ENTRY, next_cursor=NULL, rendered_sha256=DIGEST),
]}
TOOLS = (
    ("assemble_context", "Assemble authorized evidence for an exact snapshot and purpose.",
     record(snapshot=STRING, purpose=STRING), ASSEMBLED),
    ("inspect_context", "Inspect the manifest after checking current read scope.",
     record(manifest_sha256=DIGEST), INSPECTED),
    ("read_context_page", "Read one exact, authorized page using a session cursor.",
     record(manifest_sha256=DIGEST, cursor=TOKEN), PAGE),
)


class SessionReader(PAGES["Reader"]):
    def __init__(self):
        super().__init__("exact-scope")
        self.cursor_indices = {}

    def cursor(self, index):
        if index not in self.cursor_indices:
            token = token_urlsafe(24)
            self.cursor_indices[index] = token
            self.cursors[token] = index
        return self.cursor_indices[index]


def controls(control_file):
    """Fixture-owned observations. No tool accepts these as request arguments."""
    variant = json.loads(control_file.read_text())["phase"]
    scope = PAGES["SCOPE"]
    actor = PAGES["ACTOR"]
    entries = PAGES["ENTRIES"]
    sources = {(entry.snapshot, entry.source): entry for entry in entries}
    if variant in {"optional-revoked", "mandatory-revoked"}:
        revoked = "design#1" if variant == "optional-revoked" else "test#1"
        scope = replace(scope, revision="scope-2", read=scope.read - {revoked})
    elif variant == "rotated-equivalent-scope":
        scope = replace(scope, revision="scope-2")
    elif variant == "other-principal":
        actor = "observer"
    elif variant in {"missing-source", "only-new-snapshot-retained"}:
        retired = sources.pop(("snap-7", "test#1"))
        if variant == "only-new-snapshot-retained":
            sources[("snap-8", "test#1")] = replace(retired, snapshot="snap-8")
    elif variant == "changed-source-bytes":
        sources[("snap-7", "test#1")] = replace(entries[1], content="different test evidence")
    elif variant == "new-snapshot-retains-old":
        sources[("snap-8", "test#1")] = replace(entries[1], snapshot="snap-8", content="newer test evidence")
    else:
        assert variant in {"unchanged", "unknown-cursor"}
    return actor, scope, sources


async def serve(control_file):
    app = Server("llmlang-knowledge-context", version="0.1")
    reader = SessionReader()
    assembled = False
    manifest = reader.context["manifest_sha256"]

    @app.list_tools()
    async def list_tools():
        return [
            types.Tool(name=name, description=description, inputSchema=inputs,
                       outputSchema={"anyOf": [result, record(status=status("unavailable"))]})
            for name, description, inputs, result in TOOLS
        ]

    @app.call_tool()
    async def call_tool(name, args):
        nonlocal assembled
        actor, scope, sources = controls(control_file)
        if name == "assemble_context":
            expected = {key: reader.manifest[key] for key in ("snapshot", "purpose")}
            if args != expected or not reader.authorized(actor, scope):
                return UNAVAILABLE
            for reference in reader.manifest["bindings"].values():
                item = sources.get((expected["snapshot"], reference["source"]))
                if item is None or item.reference() != reference:
                    return UNAVAILABLE
            assembled = True
            return {"status": "assembled", "manifest_sha256": manifest}
        if not assembled or args.get("manifest_sha256") != manifest:
            return UNAVAILABLE
        if name == "inspect_context":
            return reader.inspect(actor, scope)
        if name == "read_context_page":
            return reader.page(actor, scope, sources, args["cursor"])
        return UNAVAILABLE

    async with stdio_server() as (incoming, outgoing):
        await app.run(incoming, outgoing, app.create_initialization_options())


if __name__ == "__main__":
    anyio.run(serve, Path(sys.argv[1]))
