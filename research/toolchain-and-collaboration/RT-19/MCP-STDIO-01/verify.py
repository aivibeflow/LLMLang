"""Drive the adapter through the upstream MCP SDK, without importing the server."""
from hashlib import sha256
import json
from pathlib import Path
import sys
from urllib.parse import quote

import anyio
from jsonschema import Draft202012Validator
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import McpError
from pydantic import AnyUrl


def digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + sha256(encoded).hexdigest()


async def verify():
    observed = {}

    def check(name, actual, expected):
        if actual != expected:
            raise AssertionError(f"{name}: {actual!r} != {expected!r}")
        if name in observed:
            raise AssertionError(f"Duplicate observation: {name}")
        observed[name] = actual

    params = StdioServerParameters(
        command=sys.executable, args=["-B", str(Path(__file__).with_name("server.py"))],
    )
    async with stdio_client(params) as (incoming, outgoing):
        async with ClientSession(incoming, outgoing) as client:
            handshake = await client.initialize()
            check("negotiated_protocol", handshake.protocolVersion, "2025-11-25")
            check("capabilities", sorted(handshake.capabilities.model_dump(exclude_none=True)),
                  ["prompts", "resources", "tools"])
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}
            check("discovered_tools", sorted(tools),
                  ["accept_workspace", "apply_change_set", "inspect_workspace", "open_workspace"])
            for tool in tools.values():
                Draft202012Validator.check_schema(tool.inputSchema)
                Draft202012Validator.check_schema(tool.outputSchema)
            mutate = Draft202012Validator(tools["apply_change_set"].inputSchema)

            async def call(name, arguments, *, expected_error=None):
                result = await client.call_tool(name, arguments)
                if len(result.content) != 1 or result.content[0].type != "text":
                    raise AssertionError("Expected one JSON text content element")
                fallback = json.loads(result.content[0].text)
                if expected_error:
                    if not result.isError or result.structuredContent is not None:
                        raise AssertionError(f"Expected a typed tool error, received {result}")
                    if fallback != {"code": expected_error}:
                        raise AssertionError(fallback)
                    return fallback["code"]
                if result.isError or fallback != result.structuredContent:
                    raise AssertionError(f"Structured result and JSON text differ: {result}")
                return fallback

            async def resource(uri):
                contents = (await client.read_resource(AnyUrl(uri))).contents
                if len(contents) != 1 or str(contents[0].uri) != uri:
                    raise AssertionError(f"Unexpected resource boundary: {contents}")
                if contents[0].mimeType != "application/json":
                    raise AssertionError(contents)
                return json.loads(contents[0].text)

            async def error_code(awaitable):
                try:
                    await awaitable
                except McpError as error:
                    return error.error.code
                raise AssertionError("Expected a JSON-RPC error")

            stable_id = "module/math+basis"
            config = "module/config"
            payload_a = {"value": 1, "refs": [config]}
            payload_b = {"value": 2, "refs": [config]}
            config_payload = {"value": 10}
            hash_a, hash_b, hash_config = (
                digest({"kind": "module", "payload": payload})
                for payload in (payload_a, payload_b, config_payload)
            )

            def root(entity_hash):
                return digest({"format_version": 1, "entities": {stable_id: entity_hash, config: hash_config}})

            def uri(snapshot, entity_id):
                return f"llmlang://snapshot/{snapshot}/entity/{quote(entity_id, safe='')}"

            base = root(hash_a)
            updated = root(hash_b)
            templates = (await client.list_resource_templates()).resourceTemplates
            check("discovered_template", [item.uriTemplate for item in templates],
                  ["llmlang://snapshot/{snapshot_id}/entity/{stable_id}"])
            resources = (await client.list_resources()).resources
            check("discovered_fixture", sorted(str(item.uri) for item in resources),
                  sorted([uri(base, stable_id), uri(base, config)]))
            prompts = (await client.list_prompts()).prompts
            check("discovered_prompt", {item.name: [arg.name for arg in item.arguments] for item in prompts},
                  {"plan_change": ["workspace_id", "snapshot_id"]})

            check("base_resource", await resource(uri(base, stable_id)),
                  {"stable_id": stable_id, "kind": "module", "payload": payload_a, "content_hash": hash_a})
            check("separate_referenced_object", (await resource(uri(base, config)))["payload"], config_payload)
            check("unknown_resource", await error_code(client.read_resource(AnyUrl(uri(base, "absent")))), -32002)
            check("malformed_resource", await error_code(client.read_resource(AnyUrl(
                uri(base, stable_id).replace("%2F", "/")))), -32602)
            a = await call("open_workspace", {"snapshot_id": base})
            b = await call("open_workspace", {"snapshot_id": base})
            workspace_a, workspace_b = a["workspace_id"], b["workspace_id"]
            check("distinct_workspace_handles", workspace_a != workspace_b, True)
            for label, workspace in (("a", a), ("b", b)):
                view = {key: value for key, value in workspace.items() if key != "workspace_id"}
                check(f"open_{label}", view, {"base_snapshot": base, "working_snapshot": base,
                                              "state": "open", "revision": 0})

            first = {"action": "update", "stable_id": stable_id, "expected_hash": hash_a,
                     "kind": "module", "payload": payload_b}
            second = {"action": "remove", "stable_id": config, "expected_hash": hash_a}
            change = {"workspace_id": workspace_a, "changeset_id": "case-1", "changes": [first]}
            check("advertised_revision_is_required", mutate.is_valid(change), False)
            check("missing_revision", await call("apply_change_set", change, expected_error="InvalidArguments"),
                  "InvalidArguments")
            contradictory = {**change, "expected_revision": 0, "changes": [{**second, "payload": {}}]}
            check("advertised_remove_has_no_payload", mutate.is_valid(contradictory), False)
            check("contradictory_remove", await call("apply_change_set", contradictory,
                                                     expected_error="InvalidArguments"), "InvalidArguments")
            invalid = {**change, "expected_revision": 0, "changes": [first, second]}
            check("advertised_late_stale_hash_is_well_formed", mutate.is_valid(invalid), True)
            check("late_stale_hash", await call("apply_change_set", invalid, expected_error="StaleObject"),
                  "StaleObject")
            check("no_partial_publication", await call("inspect_workspace", {"workspace_id": workspace_a}) == a, True)
            check("no_partial_snapshot", await error_code(client.read_resource(AnyUrl(uri(updated, stable_id)))),
                  -32002)
            valid = {**change, "expected_revision": 0}
            check("advertised_valid_change", mutate.is_valid(valid), True)
            applied = await call("apply_change_set", valid)
            check("apply_changes", {key: applied[key] for key in ("working_snapshot", "revision", "state")},
                  {"working_snapshot": updated, "revision": 1, "state": "open"})
            check("stale_revision", await call("apply_change_set", valid, expected_error="StaleRevision"),
                  "StaleRevision")
            check("workspace_b_isolated", await call("inspect_workspace", {"workspace_id": workspace_b}) == b, True)

            prompt_params = {"workspace_id": workspace_a, "snapshot_id": updated}
            prompt = await client.get_prompt("plan_change", prompt_params)
            check("scoped_user_prompt", prompt.messages[0].role, "user")
            text = prompt.messages[0].content.text
            check("prompt_binds_explicit_revision",
                  json.loads(text[text.index("{"):]) == {**prompt_params, "revision": 1}, True)
            check("prompt_rejects_wrong_snapshot", await error_code(client.get_prompt(
                "plan_change", {**prompt_params, "snapshot_id": base})), -32602)
            check("prompt_rejects_missing_workspace", await error_code(client.get_prompt(
                "plan_change", {"snapshot_id": updated})), -32602)
            check("prompt_does_not_mutate", await call("inspect_workspace", {"workspace_id": workspace_a}) == applied,
                  True)

            accept = {"workspace_id": workspace_a, "expected_revision": 1}
            check("accept_rejects_stale_revision", await call("accept_workspace", {**accept, "expected_revision": 0},
                                                              expected_error="StaleRevision"), "StaleRevision")
            accepted = await call("accept_workspace", accept)
            check("accepted_state", accepted == {**applied, "state": "accepted"}, True)
            check("accepted_workspace_cannot_mutate", await call("apply_change_set", {**valid, "expected_revision": 1},
                                                                expected_error="SemanticConflict"),
                  "SemanticConflict")
            check("snapshot_can_be_reopened",
                  (await call("open_workspace", {"snapshot_id": updated}))["working_snapshot"], updated)
            check("exact_old_snapshot", (await resource(uri(base, stable_id)))["payload"], payload_a)
            check("exact_accepted_snapshot", await resource(uri(updated, stable_id)),
                  {"stable_id": stable_id, "kind": "module", "payload": payload_b, "content_hash": hash_b})
            check("unchanged_referenced_object", (await resource(uri(updated, config)))["content_hash"], hash_config)
            spare = "module/spare"
            spare_payload = {"value": 30}
            spare_hash = digest({"kind": "module", "payload": spare_payload})
            add = {"action": "add", "stable_id": spare, "expected_hash": None,
                   "kind": "module", "payload": spare_payload}
            remove = {"action": "remove", "stable_id": config, "expected_hash": hash_config}
            edit_b = {"workspace_id": workspace_b, "expected_revision": 0,
                      "changeset_id": "case-2", "changes": [add, remove]}
            check("advertised_add_remove_pair", mutate.is_valid(edit_b), True)
            edited = await call("apply_change_set", edit_b)
            changed_root = digest({"format_version": 1, "entities": {stable_id: hash_a, spare: spare_hash}})
            check("atomic_add_remove_root", edited["working_snapshot"], changed_root)
            check("added_resource", (await resource(uri(changed_root, spare)))["payload"], spare_payload)
            check("removed_resource", await error_code(client.read_resource(AnyUrl(uri(changed_root, config)))),
                  -32002)
            check("workspace_a_remains_accepted",
                  await call("inspect_workspace", {"workspace_id": workspace_a}) == accepted, True)
    return {"observations": observed, "passed": len(observed)}


async def main():
    with anyio.fail_after(30):
        result = await verify()
    print(json.dumps(result, indent=2, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    anyio.run(main)
