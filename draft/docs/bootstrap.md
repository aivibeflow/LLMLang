# LLMLang agent bootstrap

Use the [MCP server guide](server.md) for client configuration, JSON-RPC
requests, tool arguments, and resource reads. Use the
[repository instructions](../../AGENTS.md) for checkout changes and the
[architecture RFC](../RFC.md) for design questions.

## Choose the workflow

| Task | Start with |
| --- | --- |
| Build and run a checked-in native example | Follow [Build and run native examples](#build-and-run-native-examples). |
| Edit and verify a scalar workspace over MCP | Follow [Edit and verify a scalar workspace](#edit-and-verify-a-scalar-workspace). |
| Read or edit standalone scalar source | Use the [scalar text syntax](lang.md#scalar-text-source) and the [scalar MVP CLI](../llmlang_mvp/README.md) for Calculator and Stage 0. |
| Inspect an existing package | Import its dependencies and the package, then use [MCP resource reads](server.md#tools-and-resources) to inspect the returned snapshot's objects and links. |

## Run the Python MCP client

Build the server and set up the toolchain environment first. From the repository root, use the bundled Python 3.10+ client to discover the current tool schemas and resource URI templates. Each CLI invocation starts a server process. Use one Python API session for related requests that share a workspace. [Build and connection instructions](server.md#build-and-connect) · [Client source](../server/mcp_client.py) · [CLI and API reference](../server/README.md#python-stdio-client)

```sh
state_dir=$(mktemp -d)
server=draft/server/target/debug/llmlang-server

python3 draft/server/mcp_client.py tools/list --server "$server" --state-dir "$state_dir"
python3 draft/server/mcp_client.py resources/templates/list --server "$server" --state-dir "$state_dir"
```

In the same shell, use the Python API to create a package and read the workspace over one connection.

```sh
PYTHONPATH=draft/server python3 - "$server" "$state_dir" <<'PY'
import json
import sys

from mcp_client import connect

server, state_dir = sys.argv[1:]
with connect([server, "--state-dir", state_dir]) as client:
    result = client.call_tool("create_package", {
        "name": "answer", "profile": "scalar", "language_version": "0.1.0",
    })
    if result.get("isError"):
        raise SystemExit(result["content"][0]["text"])
    workspace_id = result["structuredContent"]["workspace_id"]
    resource = client.request("resources/read", uri=f"llmlang://workspace/{workspace_id}")
    print(json.dumps(json.loads(resource["contents"][0]["text"]), indent=2))
PY
```

## Build and run native examples

Use a Linux x86-64 checkout with Rust 1.85.1 or newer, the
`x86_64-unknown-linux-gnu` Rust target, Cargo, a native linker, and GNU
`objcopy`. The repository test client uses Python 3.10 or newer and
`readelf`. Run these commands from
the repository root.

```sh
cargo build --locked --manifest-path draft/server/Cargo.toml
python3 -B draft/server/tests/native_build_e2e.py draft/server/target/debug/llmlang-server
```

The test client starts its own MCP server and builds and runs both Hello World
examples and all five syscall programs. This workflow uses `rustc` on `PATH`
or from `RUSTC`. Stage 0, Boogie, and Z3 are needed for the scalar workflow
below.

To build one package with your MCP client, configure it to launch
`$PWD/draft/server/target/debug/llmlang-server` over stdio with
`--state-dir` followed by an absolute path to a private directory. On Linux,
`mktemp -d` provides a suitable directory. The client initializes the session
before calling tools. [Client configuration and handshake](server.md#build-and-connect)

1. Call `import_package` with a `path` containing the absolute path to
   `draft/stdlib` (version `0.1.0`).
2. For a syscall example, import `draft/examples/linux.syscalls` (version
   `v6.12`) in the same session.
3. Import the example directory and use its returned `snapshot_id` as the
   `snapshot_id` argument to `build_package`. Set `target` to
   `linux-x86_64`.
4. Run the file at the returned `artifact` path. Both Hello World examples
   write `Hello, world!` followed by a newline and exit with status 0.
   For executables, the returned `debug_artifact` is the companion debug file.

| Examples | Package path |
| --- | --- |
| Hello World through the standard library | `draft/examples/0001-hello-world` |
| Hello World through the Linux write interface | `draft/examples/0009-syscall-hello-world` |
| Syscall programs for echo, copy, pipe readiness, child exit, and TCP echo | `draft/examples/0004-syscall-echo` through `draft/examples/0008-syscall-tcp-echo` |

The server builds from the SPG package tables. Native import and build return
`verification_status: "unchecked"`. Report that status separately from any
observed execution results. [Example catalog](../examples/README.md) · [Native build example](server.md#build-an-existing-native-program)

## Edit and verify a scalar workspace

Build Stage 0 and configure the verifier before starting the server. Set
`LLMLANG_STAGE0`, `BOOGIE`, and `Z3` as described in the
[server setup](server.md#build-and-connect).

1. Connect to the server and use `tools/list` and `resources/templates/list`
   to discover the interface. For a local session, use the [Python MCP client](#run-the-python-mcp-client).
   Call `create_package` with `profile: "scalar"`
   and `language_version: "0.1.0"`. Keep the returned `workspace_id` and
   `revision`.
2. Describe the behavior with typed signatures, contracts, and implementation
   bodies. Submit the batch with `apply_change_set`, the current
   `expected_revision`, and a fresh idempotency key. Pin the exact callee
   implementation and required contract for each call.
3. Call `verify_workspace` with the returned revision. Check
   `report.report.status` and inspect diagnostics when it differs from
   `VERIFIED`. The report applies to that revision.

Scalar workspaces last for the lifetime of the server process.
`commit_workspace` returns `UnsupportedProfile` for these workspaces.
[Structured scalar syntax](lang.md#scalar-mcp-authoring) · [Complete verification example](server.md#verify-a-scalar-workspace) · [Conflict recovery](server.md#recover-from-a-conflict-or-interrupted-request)
