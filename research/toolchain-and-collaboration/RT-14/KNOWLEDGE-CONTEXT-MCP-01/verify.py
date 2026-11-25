"""Compare RT-19 MCP stdio responses with direct Knowledge Context calls."""
import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import platform
import runpy
from subprocess import check_output
import sys
from tempfile import TemporaryDirectory

import anyio
from jsonschema import Draft202012Validator
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
REFERENCE = HERE.parent / "KNOWLEDGE-CONTEXT-PAGES-01/run.py"
PAGES = runpy.run_path(str(REFERENCE))
PIN = "ef270e6eb668454752af79c976d7db806e98e74b"
SCHEDULES = (
    ("unchanged", 3), ("optional-revoked", 1), ("mandatory-revoked", 1),
    ("rotated-equivalent-scope", 1), ("other-principal", 1), ("unknown-cursor", 1),
    ("missing-source", 1), ("only-new-snapshot-retained", 1), ("changed-source-bytes", 1),
    ("new-snapshot-retains-old", 3),
)
EXPECTED_ARGUMENTS = {
    "assemble_context": ["snapshot", "purpose"],
    "inspect_context": ["manifest_sha256"],
    "read_context_page": ["manifest_sha256", "cursor"],
}


def normalize(row):
    return {key: bool(value) if key in {"first_cursor", "next_cursor"} else value
            for key, value in row.items()}


def phase(path, name):
    staged = path.with_suffix(".new")
    staged.write_text(json.dumps({"phase": name}))
    staged.replace(path)


async def schedule(client, control, variant, expected, prior_cursor):
    handshake = await client.initialize()
    assert handshake.protocolVersion == "2025-11-25"
    tools = {item.name: item for item in (await client.list_tools()).tools}
    assert set(tools) == set(EXPECTED_ARGUMENTS)
    for name, tool in tools.items():
        Draft202012Validator.check_schema(tool.inputSchema)
        Draft202012Validator.check_schema(tool.outputSchema)
        assert tool.inputSchema["required"] == EXPECTED_ARGUMENTS[name]
        assert not tool.inputSchema["additionalProperties"]

    async def call(name, args):
        result = await client.call_tool(name, args)
        assert not result.isError and len(result.content) == 1 and result.content[0].type == "text"
        body = result.structuredContent
        assert body == json.loads(result.content[0].text)
        Draft202012Validator(tools[name].outputSchema).validate(body)
        return body

    correct = {"snapshot": "snap-7", "purpose": "review-quota-change"}
    manifest_request = {"manifest_sha256": PAGES["Reader"]("exact-scope").context["manifest_sha256"]}
    unavailable = PAGES["UNAVAILABLE"]
    fresh_assembly_denials = {
        "optional-revoked", "mandatory-revoked", "rotated-equivalent-scope", "other-principal",
        "missing-source", "only-new-snapshot-retained", "changed-source-bytes",
    }
    assert await call("inspect_context", manifest_request) == unavailable
    assert await call("assemble_context", {**correct, "snapshot": "snap-8"}) == unavailable
    assert await call("assemble_context", {**correct, "purpose": "other-purpose"}) == unavailable
    invalid = await client.call_tool("assemble_context", {**correct, "actor": "reviewer"})
    assert invalid.isError and invalid.structuredContent is None
    assembled = await call("assemble_context", correct)
    assert assembled == {"status": "assembled", **manifest_request}
    opened = await call("inspect_context", manifest_request)
    cursor = opened["first_cursor"]
    if prior_cursor is not None:
        assert cursor != prior_cursor
        assert await call("read_context_page", {**manifest_request, "cursor": prior_cursor}) == unavailable
    wrong_manifest = {"manifest_sha256": "0" * 64, "cursor": cursor}
    assert await call("read_context_page", wrong_manifest) == unavailable
    first = await call("read_context_page", {**manifest_request, "cursor": cursor})
    phase(control, variant)
    fresh_assembly = await call("assemble_context", correct)
    assert (fresh_assembly == unavailable) == (variant in fresh_assembly_denials)
    fresh_inspection = await call("inspect_context", manifest_request)
    second_cursor = "never-issued-fixture-cursor" if variant == "unknown-cursor" else first["next_cursor"]
    second = await call("read_context_page", {**manifest_request, "cursor": second_cursor})
    assert second == await call("read_context_page", {**manifest_request, "cursor": second_cursor})
    third = (await call("read_context_page", {**manifest_request, "cursor": second["next_cursor"]})
             if second["status"] == "page" else unavailable)
    direct = PAGES["schedule"]("exact-scope", variant, False)
    assert normalize(opened) == normalize(direct["opened"])
    assert normalize(fresh_inspection) == normalize(direct["fresh_inspection"])
    assert [normalize(page) for page in (first, second, third)] == [normalize(page) for page in direct["pages"]]
    assert sum(page["status"] == "page" for page in (first, second, third)) == expected
    return {
        "pages": [normalize(page) for page in (first, second, third)],
        "fresh_inspection": normalize(fresh_inspection),
        "fresh_assembly": fresh_assembly,
        "cross_session_cursor_rejected": prior_cursor is not None,
    }, cursor


async def replay(control):
    parameters = StdioServerParameters(command=sys.executable,
                                      args=["-B", str(HERE / "server.py"), str(control)])
    results = {}
    prior = None
    for variant, count in SCHEDULES:
        phase(control, "unchanged")
        async with stdio_client(parameters) as (incoming, outgoing):
            async with ClientSession(incoming, outgoing) as client:
                results[variant], prior = await schedule(client, control, variant, count, prior)
    return results


async def check(output):
    pins = {}
    for path in (REFERENCE, PAGES["REFERENCE"]):
        location = path.relative_to(ROOT).as_posix()
        base = check_output(["git", "show", f"{PIN}:{location}"], cwd=ROOT)
        assert path.read_bytes() == base
        pins[location] = sha256(base).hexdigest()
    with TemporaryDirectory() as temporary:
        with anyio.fail_after(90):
            results = await replay(Path(temporary) / "phase.json")
    output.write_text(json.dumps({
        "snapshot": PIN, "pinned_reference_sha256": pins, "python": platform.python_version(),
        "dependencies": {name: version(name) for name in ("mcp", "anyio", "jsonschema", "pydantic")},
        "protocol": "2025-11-25", "cases": results,
    }, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    anyio.run(check, parser.parse_args().output)
