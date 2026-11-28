"""Exercise llmlang-server through its MCP stdio protocol.

Run with the built server executable as the first argument. The server process
inherits the verifier and compiler tool paths from the test environment.
"""

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

CLIENT = Path(__file__).resolve().parents[1] / "mcp_client.py"
sys.path.insert(0, str(CLIENT.parent))
from mcp_client import RpcError, connect


class TestSession:
    def __init__(self, client):
        self.client = client
        self.request = client.request

    def call(self, name, arguments, *, succeeds=True):
        result = self.client.call_tool(name, arguments)
        assert result.get("isError", False) == (not succeeds), (name, result)
        if succeeds:
            assert "structuredContent" in result, result
            return result["structuredContent"]
        if "structuredContent" in result:
            return result["structuredContent"]
        return json.loads(result["content"][0]["text"])


@contextmanager
def server(executable, state_dir, python):
    with connect([executable, "--state-dir", state_dir, "--python", python]) as client:
        assert {"tools", "resources"} <= client.server["capabilities"].keys(), client.server
        assert client.request("ping") == {}
        yield TestSession(client)


def local(name):
    return {"local": name}


SIGNATURE = "() -> I64"


def implementation(name, body, contract):
    return {
        "op": "put_function",
        "id": name,
        "signature": SIGNATURE,
        "canonical_body": [["return", body]],
        "provided_contract": contract,
    }


def constant(value):
    return ["i64", value]


def contract(name, value):
    return {
        "op": "put_contract",
        "id": name,
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
        "name": name, "language_version": "0.1.0.0.0",
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
        "invalid-signature": [
            {**implementation("bad-signature", constant(42), accepted["identities"]["contract"]),
             "signature": "() -> i64"},
        ],
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
    for package in ("builtin.extra", "stdlib", "builtin"):
        workspace = create(client, package)
        request = apply_request(workspace["workspace_id"], workspace["revision"],
                                "builtin-access", operations)
        allowed = package == "builtin"
        result = client.call("apply_change_set", request, succeeds=allowed)
        if allowed:
            assert "failure" in result["identities"], result
        else:
            assert result["code"] == "ValidationFailed", result
            assert result["message"] == (
                f"builtin__fail may only be used in package builtin (found in package {package})"
            ), result
            current = client.call("inspect_workspace", {"workspace_id": workspace["workspace_id"]})
            assert current["revision"] == workspace["revision"], current


def read_object(client, uri):
    result = client.request("resources/read", uri=uri)
    assert result["contents"][0]["uri"] == uri, result
    return json.loads(result["contents"][0]["text"])


def check_scalar_source(client):
    workspace = create(client, "source")
    workspace_id = workspace["workspace_id"]
    signature = "(value: I64) -> I64"
    body = "{\n    let shifted = value + 1;\n    if value == 0 { return 1; }\n    return shifted;\n}"
    function = {
        "op": "put_function", "id": "step", "signature": signature,
        "provided_contract": local("contract"), "canonical_body": body,
    }
    first = client.call("apply_change_set", apply_request(workspace_id, 0, "source", [
        {"op": "set_version", "version": "1", "expected_version": None},
        {"op": "put_contract", "id": "contract", "rules": [
            {"kind": "requires", "predicate": "0 <= value <= 10"},
            {"kind": "ensures", "predicate": "result == value + 1"},
        ]},
        function,
    ]))
    callee, required = (first["identities"][name] for name in ("step", "contract"))
    caller_body = f'{{ return call("{callee}", "{required}", value); }}'
    second = client.call("apply_change_set", apply_request(workspace_id, 1, "caller", [
        {**function, "id": "caller", "canonical_body": caller_body, "provided_contract": required},
        {"op": "put_interface", "id": "public", "name": "source.step", "public_contract": required},
        {"op": "bind", "interface": local("public"), "implementation": local("caller"),
         "expected_implementation": None},
    ]))
    caller = second["identities"]["caller"]
    base = f"llmlang://workspace/{workspace_id}/object/functions/"
    assert read_object(client, base + callee)["row"]["canonical_body"] == body
    saved = read_object(client, base + caller)
    assert saved["row"]["canonical_body"] == caller_body
    assert {"relation": "Callee", "uri": base + callee} in saved["outgoing"]
    verification = client.call("verify_workspace", scope(workspace, 2))
    assert verification["failures"] == []
    verified = verification["report"]
    assert verified["ok"], verified
    proof = verified["report"]
    assert {"caller_impl_hash": caller, "callee_impl_hash": callee,
            "required_contract_hash": required} in proof["calls"]
    ir = proof["contract_ir"][callee][required]
    assert ir["schema"] == "llmlang-contract-ir/scalar-v1" and ir["requires"][0]["op"] == "and"
    assert ir["ensures"][0]["args"][1]["args"][1] == {"op": "literal", "type": "Int", "value": "1"}

    unsupported = client.call("apply_change_set", apply_request(workspace_id, 2, "unsupported", [
        {**function, "provided_contract": required, "canonical_body": "{\n    loop {}\n}"},
    ]), succeeds=False)
    assert "line 2, column 5" in unsupported["message"], unsupported
    missing = client.call("apply_change_set", apply_request(workspace_id, 2, "missing", [
        {**function, "provided_contract": required,
         "canonical_body": f'{{ return call("{"0" * 64}", "{required}", value); }}'},
    ]), succeeds=False)
    assert missing["code"] == "ValidationFailed", missing
    unchanged = client.call("inspect_workspace", {"workspace_id": workspace_id})
    assert unchanged["revision"] == 2, unchanged

    changed = client.call("apply_change_set", apply_request(workspace_id, 2, "counterexample", [
        {**function, "provided_contract": required, "canonical_body": "{ return value + 2; }",
         "previous": callee, "expected_hash": read_object(client, base + callee)["content_hash"]},
    ]))
    assert caller in changed["affected_functions"], changed
    commit = client.call("commit_workspace", scope(workspace, 3), succeeds=False)
    assert commit["code"] == "VerificationFailed", commit
    verification = commit["verification"]
    assert verification["workspace_id"] == workspace_id and verification["revision"] == 3
    assert client.call("inspect_workspace", {"workspace_id": workspace_id})["state"] == "open"
    rejected = verification["report"]
    assert not rejected["ok"] and rejected["report"]["status"] == "REJECTED", rejected
    failure, = verification["failures"]
    assert failure["kind"] == "body-postcondition" and failure["contract_role"] == "provided"
    failed_function = failure["function"]
    assert failed_function["impl_hash"] == changed["identities"]["step"]
    assert failed_function["canonical_body"] == "{ return value + 2; }"
    assert failed_function["function_signature"]["function_signature_content"] == signature
    assert failed_function["function_signature"]["typed_signature"] == {
        "parameters": [{"name": "value", "type": "I64"}], "result": "I64",
    }
    assert "typed_signature" not in failure["contract"]
    assert failed_function["provided_contract"] == failure["contract"]
    assert failure["contract"]["contract_hash"] == required and failure["contract"]["ir"] == ir
    assert any(rule.get("predicate") == "result == value + 1" for rule in failure["contract"]["rules"])
    assert failure["evidence"]["status"] == "confirmed-source"

    related = client.call("apply_change_set", apply_request(workspace_id, 3, "related-contracts", [
        {"op": "put_contract", "id": "wider", "rules": [
            {"kind": "requires", "predicate": "value == -1"},
            {"kind": "ensures", "predicate": "result == value + 1"},
        ]},
        {**function, "id": "bad_caller", "canonical_body": caller_body,
         "provided_contract": local("wider")},
        {"op": "put_interface", "id": "bad_interface", "name": "source.wider",
         "public_contract": local("wider")},
        {"op": "bind", "interface": local("bad_interface"), "implementation": callee,
         "expected_implementation": None},
    ]))
    commit = client.call("commit_workspace", scope(workspace, 4), succeeds=False)
    assert commit["code"] == "VerificationFailed", commit
    verification = commit["verification"]
    by_kind = {item["kind"]: item for item in verification["failures"]}
    failed_call = by_kind["callee-precondition"]
    assert failed_call["function"]["impl_hash"] == related["identities"]["bad_caller"]
    assert failed_call["contract_role"] == "required" and failed_call["contract"]["contract_hash"] == required
    assert failed_call["callee"]["impl_hash"] == callee
    assert failed_call["evidence"]["invalid_call"]["arguments"] == {"value": -1}
    refinement = by_kind["provider-precondition"]
    assert refinement["function"]["impl_hash"] == callee
    assert refinement["contract"]["contract_hash"] == required
    assert refinement["comparison_contract"]["contract_hash"] == related["identities"]["wider"]


def check_contract_reuse(client):
    workspace = create(client, "contract_reuse")
    workspace_id = workspace["workspace_id"]
    spec = {"op": "put_contract", "id": "spec", "rules": [
        {"kind": "ensures", "predicate": "result >= 0"},
    ]}
    no_args = implementation("constant", constant(1), local("spec"))
    one_arg = {**no_args, "id": "with_arg", "signature": "(value: I64) -> I64"}
    with_arg = {**spec, "id": "needs_arg", "rules": [
        {"kind": "ensures", "predicate": "result >= value"},
    ]}
    applied = client.call("apply_change_set", apply_request(workspace_id, 0, "reuse", [
        {"op": "set_version", "version": "1", "expected_version": None},
        spec, no_args, one_arg, with_arg, {**spec, "id": "same_spec"},
        {"op": "put_interface", "id": "api", "name": "contract_reuse.get",
         "public_contract": local("spec")},
        {"op": "put_interface", "id": "api_with_arg", "name": "contract_reuse.needs_arg",
         "public_contract": local("needs_arg")},
        {"op": "bind", "interface": local("api"), "implementation": local("constant"),
         "expected_implementation": None},
        {"op": "bind", "interface": local("api"), "implementation": local("with_arg"),
         "arch": "aarch64", "os": "linux", "expected_implementation": None},
    ]))
    identities = applied["identities"]
    assert identities["spec"] == identities["same_spec"]
    exports = client.call("inspect_workspace", {"workspace_id": workspace_id})["exports"]
    assert {row["interface_hash"] for row in exports} == {identities["api"]}
    assert {row["impl_hash"] for row in exports} == {identities["constant"], identities["with_arg"]}
    verification = client.call("verify_workspace", scope(workspace, 1))
    assert verification["report"]["ok"], verification
    typed = verification["report"]["report"]["contract_ir"]
    assert typed[identities["constant"]][identities["spec"]]["parameters"] == []
    assert typed[identities["with_arg"]][identities["spec"]]["parameters"][0]["name"] == "value"
    rejected = client.call("apply_change_set", apply_request(workspace_id, 1, "missing_param", [
        {"op": "bind", "interface": identities["api_with_arg"],
         "implementation": identities["constant"], "expected_implementation": None},
    ]), succeeds=False)
    assert rejected["code"] == "ValidationFailed" and "value" in rejected["message"], rejected
    assert identities["constant"] in rejected["message"], rejected
    rejected = client.call("apply_change_set", apply_request(workspace_id, 1, "wrong_result_type", [
        {**no_args, "signature": "() -> Bool", "canonical_body": "{ return true; }",
         "provided_contract": identities["spec"]},
    ]), succeeds=False)
    assert rejected["code"] == "ValidationFailed", rejected
    assert client.call("inspect_workspace", {"workspace_id": workspace_id})["revision"] == 1


def check_source_arithmetic(client):
    workspace = create(client, "arithmetic")
    ops = [{"op": "set_version", "version": "1", "expected_version": None}]
    for name, body, rules in [
        ("truncate", "{ return -5 / 2; }", [{"kind": "ensures", "predicate": "result == -2"}]),
        ("zero", "{ return 1 / 0; }", [
            {"kind": "ensures", "predicate": False},
            {"kind": "error_declaration", "error_label": "DivisionByZero"},
        ]),
        ("overflow", "{ return -9223372036854775808 / -1; }", [
            {"kind": "ensures", "predicate": False},
            {"kind": "error_declaration", "error_label": "ArithmeticOverflow"},
        ]),
    ]:
        contract_id = f"{name}_contract"
        ops.extend([
            {"op": "put_contract", "id": contract_id, "rules": rules},
            {"op": "put_function", "id": name, "signature": SIGNATURE,
             "provided_contract": local(contract_id), "canonical_body": body},
        ])
    client.call("apply_change_set", apply_request(workspace["workspace_id"], 0, "arithmetic", ops))
    verified = client.call("verify_workspace", scope(workspace, 1))["report"]
    assert verified["ok"], verified


def check_documentation(client):
    draft = Path(__file__).resolve().parents[2]
    prefix = "llmlang://doc/"
    pages = {
        "bootstrap.md": "docs/bootstrap.md",
        "server.md": "docs/server.md",
        "lang.md": "docs/lang.md",
        "examples.md": "examples/README.md",
        "rfc.md": "RFC.md",
    }
    listed = client.request("resources/list")["resources"]
    assert prefix + "bootstrap.md" in client.client.server["instructions"]
    assert {item["uri"] for item in listed} == {prefix + path for path in (*pages, "index.md")}
    assert all(item["mimeType"] == "text/markdown" for item in listed)

    def read(path):
        uri = prefix + path
        content, = client.request("resources/read", uri=uri)["contents"]
        assert content["uri"] == uri and content["mimeType"] == "text/markdown", content
        return content["text"]

    bootstrap = read("bootstrap.md")
    assert prefix + "index.md" in bootstrap
    index = read("index.md")
    for path, source in pages.items():
        assert f"]({prefix}{path})" in index
        if path != "bootstrap.md":
            assert f"]({prefix}{path})" in bootstrap
        assert read(path) == (draft / source).read_text(encoding="utf-8")

    for path in ("missing.md", "../AGENTS.md", "%2e%2e/AGENTS.md"):
        try:
            read(path)
        except RpcError as error:
            assert error.error["data"]["code"] == "MissingReference", error.error
        else:
            raise AssertionError(f"Unavailable document was returned: {path}")


def check_balance_proof(client):
    draft = CLIENT.parents[1]
    client.call("import_package", {"path": str(draft / "builtin")})
    package = draft / "examples" / "0010-balance-transfer"
    imported = client.call("import_package", {"path": str(package)})
    workspace = client.call("open_workspace", {"snapshot_id": imported["snapshot_id"]})
    functions = json.loads((package / "functions.json").read_text())
    core, = (row for row in functions if "if recipient" in row["canonicalBody"])
    main, = (row for row in functions if row != core)
    reply = client.call("verify_workspace", scope(workspace))
    report = reply["report"]["report"]
    assert report["status"] == "UNSUPPORTED", report
    core_check, = report["checks"]
    assert core_check["body"] == core_check["refinement"] == "verified", core_check
    assert report["identities"][core_check["function"]]["implementation_hash"] == core["implHash"]
    outstanding, = report["unsupported"]
    assert outstanding["kind"] == "callee_precondition", outstanding
    assert outstanding["implementation_hash"] == main["implHash"]
    assert outstanding["callee_impl_hash"] == core["implHash"]
    assert outstanding["contract_hash"] == core["providedContractHash"]
    assert len(report["no_behavioral_obligations"]) == 1  # builtin.write

    body = core["canonicalBody"].replace("return destination + amount;", "return destination;")
    changes = client.call("apply_change_set", apply_request(workspace["workspace_id"], 0, "break-conservation", [{
        "op":"put_function", "id":"broken",
        "signature":"(source: U64, destination: U64, amount: U64, recipient: Bool) -> U64",
        "canonical_body": body, "provided_contract": core["providedContractHash"],
    }]))
    rejected = client.call("verify_workspace", scope(changes))
    assert rejected["report"]["report"]["status"] == "REJECTED", rejected
    assert any(item["function"]["impl_hash"] == changes["identities"]["broken"]
               and item["kind"] == "body-postcondition"
               and item["contract"]["contract_hash"] == core["providedContractHash"]
               for item in rejected["failures"]), rejected


def check_committed_library(client, executable, root, python):
    workspace = create(client, "verified")
    signature = "(value: I64) -> I64"
    applied = client.call("apply_change_set", apply_request(workspace["workspace_id"], 0, "library", [
        {"op": "set_version", "version": "1", "expected_version": None},
        {"op": "put_contract", "id": "arithmetic", "rules": [
            {"kind": "ensures", "predicate": "result == value + 1"},
            {"kind": "error_declaration", "error_label": "ArithmeticOverflow"},
            {"kind": "error_guard", "error_label": "ArithmeticOverflow",
             "predicate": "value == 9223372036854775807"},
        ]},
        {"op":"put_function", "id":"next", "signature": signature,
         "canonical_body":"{ return value + 1; }", "provided_contract": local("arithmetic")},
        {"op":"put_interface", "id":"next_api", "name":"verified.next",
         "public_contract": local("arithmetic")},
        {"op":"bind", "interface": local("next_api"), "implementation":local("next"),
         "expected_implementation": None},
    ]))
    committed = client.call("commit_workspace", scope(workspace, applied["revision"]))
    package = Path(committed["package_path"])
    assert json.loads((package / "manifest.json").read_text())["profile"] == "llmlang.spg.tables.v9"
    assert all("profile" not in row and "typedSignature" not in row for row in json.loads((package / "contracts.json").read_text()))
    with server(executable, root / "reloaded", python) as fresh:
        loaded = fresh.call("import_package", {"path": str(package)})
        assert loaded["snapshot_id"] == committed["snapshot_id"]
        output = fresh.call("build_package", {
            "snapshot_id": loaded["snapshot_id"], "target": "linux-x86_64",
        })

    symbol = output["exports"]["verified.next"]
    source = root / "proof-harness.rs"
    source.write_text(
        f"fn main() {{\n"
        f"    assert_eq!(llmlang_native::{symbol}(41), Ok(42));\n"
        f"    assert_eq!(llmlang_native::{symbol}(i64::MAX),"
        " Err(llmlang_native::LlmlangError::ArithmeticOverflow));\n"
        "}\n",
        encoding="utf-8",
    )
    harness = root / "proof-harness"
    subprocess.run([os.environ.get("RUSTC", "rustc"), "--crate-name", "proof_harness",
                    "--edition=2021", "--extern", f"llmlang_native={output['artifact']}",
                    "-o", str(harness), str(source)], check=True, timeout=30)
    subprocess.run([harness], check=True, timeout=10)


def exercise(executable, root, python):
    state = root / "author"
    with server(executable, state, python) as client:
        check_documentation(client)
        check_balance_proof(client)
        check_scalar_source(client)
        check_contract_reuse(client)
        check_source_arithmetic(client)
        templates = client.request("resources/templates/list")["resourceTemplates"]
        workspace_template = next(template["uriTemplate"] for template in templates
                                  if template["name"] == "workspace")
        tools = {tool["name"]: tool for tool in client.request("tools/list")["tools"]}
        names = {
            "create_package", "open_workspace", "inspect_workspace", "apply_change_set",
            "verify_workspace", "commit_workspace", "build_package", "import_package",
        }
        assert names <= tools.keys(), tools
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
        assert stored["workspaces"][workspace["workspace_id"]]["program"]["tables"]["functions"], stored
        workspace_uri = workspace_template.format(workspace_id=workspace["workspace_id"])
        main = read_object(client, f"{workspace_uri}/object/functions/{identities['main']}")
        helper = read_object(client, f"{workspace_uri}/object/functions/{identities['add']}")
        assert any(link["uri"].endswith(f"/functions/{identities['add']}") for link in main["outgoing"]), main
        assert any(link["uri"].endswith(f"/functions/{identities['main']}") for link in helper["incoming"]), helper
        content_hashes = {"add": helper["content_hash"], "main": main["content_hash"]}

        assert client.call("apply_change_set", args) == applied
        verified = client.call("verify_workspace", scope(workspace, applied["revision"]))
        assert verified["report"]["ok"], verified
        stale = client.call("commit_workspace", scope(workspace), succeeds=False)
        assert stale["code"] == "StaleRevision" and "verification" not in stale, stale

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

        bind = {
            "op": "bind", "interface": second["identities"]["public_v2"],
            "implementation": second["identities"]["main_v2"], "expected_implementation": None,
        }
        invalid = client.call("apply_change_set", apply_request(
            workspace["workspace_id"], second["revision"], "bad-target", [{**bind, "arch": "armv7", "os": "linux"}],
        ), succeeds=False)
        assert invalid["code"] == "InvalidArguments", invalid
        variants = client.call("apply_change_set", apply_request(
            workspace["workspace_id"], second["revision"], "target", [{**bind, "arch": "x86_64", "os": "linux"}, {**bind, "os": "linux"}],
        ))
        assert {(row["arch"], row["os"]) for row in variants["exports"]} == {("", ""), ("x86_64", "linux"), ("", "linux")}, variants
        removed = client.call("apply_change_set", apply_request(
            workspace["workspace_id"], variants["revision"], "remove-target", [{
                "op": "unbind", "name": "main", "arch": "x86_64", "os": "linux",
                "expected_implementation": bind["implementation"],
            }],
        ))
        assert {(row["arch"], row["os"]) for row in removed["exports"]} == {("", ""), ("", "linux")}, removed
        assert not list((state / "packages").iterdir())
        assert not (state / "pending-package").exists()
        stored = json.loads((state / "state.json").read_bytes())
        assert stored["workspaces"][workspace["workspace_id"]]["program"]["tables"]["functions"], stored

    with server(executable, state, python) as client:
        reopened = client.call("inspect_workspace", {"workspace_id": workspace["workspace_id"]})
        assert reopened["revision"] == removed["revision"]
        check_committed_library(client, executable, root, python)

    # A fresh CLI session discovers the same schemas and reads the saved workspace.
    command = [sys.executable, "-B", CLIENT]
    launch = ["--server", executable, "--state-dir", state, "--python", python]
    listed = subprocess.check_output([*command, "tools/list", *launch], timeout=10)
    assert json.loads(listed)["tools"] == list(tools.values())
    saved = subprocess.check_output(
        [*command, "resources/read", "-", *launch], input=json.dumps({"uri": workspace_uri}),
        text=True, timeout=10,
    )
    assert json.loads(json.loads(saved)["contents"][0]["text"])["revision"] == removed["revision"]

    print("MCP editing, verification, publication, and compilation checks passed")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--python", default="python3")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="llmlang-mcp-e2e-") as directory:
        exercise(args.executable.resolve(), Path(directory), args.python)


if __name__ == "__main__":
    main()
