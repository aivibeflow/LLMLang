# LLMLang Server MVP

This Linux server implements in-memory scalar editing and verification, and native
package import and compilation over MCP stdio. Run a
server per local OS principal with an owner-private state directory. Its
Toolchain operations are also available through the Rust `Server` API.
The service serializes operations within one process and holds an exclusive
lock on the state directory. A local MCP client uses the authority of the
process that launches it.

The Rust sources are in [draft/src/server](../src/server).

## Build and run

Use Rust 1.85.1 or newer, Python 3.10 or newer, Boogie with its .NET runtime,
and Z3. Native Linux x86-64 executable builds also use GNU `objcopy`. Run the following from the
repository root.

```sh
cargo build --locked --manifest-path draft/server/Cargo.toml

export BOOGIE=/path/to/boogie
export Z3=/path/to/z3

draft/server/target/debug/llmlang-server --state-dir /path/to/private-state
```

Configure the MCP client to launch that last command. The server creates its
state directory if it is missing. It accepts `--python` and `--backend`
overrides for the trusted scalar toolchain. Its default backend is
[scalar.py](scalar.py), which uses the [scalar verifier](scalar_verification/verify.py). The MCP stream uses one JSON-RPC message per line.

## Python stdio client

The bundled [client](mcp_client.py) uses the Python 3.10+ standard library.
It launches the server with the command after `--server` and inherits the
toolchain environment set above. List tools with their input and output
schemas, then pass any advertised tool name and its arguments as JSON.

```sh
python3 draft/server/mcp_client.py tools/list \
  --server draft/server/target/debug/llmlang-server --state-dir /path/to/private-state
python3 draft/server/mcp_client.py tools/call \
  '{"name":"create_package","arguments":{"name":"demo","profile":"scalar","language_version":"0.1.0"}}' \
  --server draft/server/target/debug/llmlang-server --state-dir /path/to/private-state
python3 draft/server/mcp_client.py resources/templates/list \
  --server draft/server/target/debug/llmlang-server --state-dir /path/to/private-state
```

The first argument is an MCP method. Pass `-` in place of the JSON object to
read parameters from stdin. Use `resources/read` with `{"uri":"…"}` to read
a resource. The client initializes the session automatically. The `initialize`
command displays the negotiated protocol version and server capabilities.
The CLI prints complete MCP results, including tool error results, to stdout.
It prints JSON-RPC errors to stderr and exits with status 1 for either kind
of error. Set `--timeout` before `--server` to change the 180-second response
timeout.

Each CLI invocation starts a new server process. To work with scalar workspaces
or imported packages across multiple requests, keep a single connection open
with `connect` from `mcp_client.py` (with `draft/server` on Python's module search path).

```python
from mcp_client import connect

with connect(["draft/server/target/debug/llmlang-server", "--state-dir", "./private-state"]) as client:
    tools = client.request("tools/list")["tools"]
    result = client.call_tool("create_package", {
        "name": "demo", "profile": "scalar", "language_version": "0.1.0",
    })
```

Tool names, schemas, and resource templates come from the running server.
New tools and argument changes are available through the same API. The
scalar and native end-to-end tests exercise this client against the server
built from the same checkout.

## Package lifecycle

Use `tools/list` to discover the input and output schemas. Start with
`create_package` using `profile: "scalar"` and `language_version: "0.1.0"`.
With `apply_change_set`, select a package version and submit structured
contracts, implementations, interfaces, and bindings. A batch can refer to a
new object with `{"local":"its_request_id"}`. Use
`resources/templates/list` and `resources/read` to inspect a function, its
Content Hash, and its dependency links. For a complete example request, see
[the MCP integration test](tests/mcp_e2e.py).

`bind` and `unbind` take an optional `platform` that defaults to `""`.
Their preconditions apply to the named platform row. All rows for a public
name in the version must refer to the same interface revision.

`apply_change_set` derives call compatibility obligations for the candidate
and validates it before advancing the revision. Each obligation records the
caller, callee, and caller-required contract. An obligation has no verification
outcome until it has been checked.
`verify_workspace` produces a preview. Scalar workspaces live for the
lifetime of the server process. `commit_workspace` returns `UnsupportedProfile`
for a scalar workspace. A successful source-backed commit requires verification
and writes a package with per-table debug ProtoJSON to
`<state-dir>/packages/<package-name>/<version>`.

Each function row points to its canonical signature text in the
`function_signatures` table. The server stages shared signature rows in the
same Change Set as their functions and restores typed signatures for
verification and compilation.

The package contains the standard SPG manifest, table dumps and indexes, plus
`package.json` with the package name, version selection, optional entry point,
and snapshot ID used by this server. Import verifies the package, reconstructs
its identity, and registers the snapshot. Import dependencies before importing a package that uses them. A dependency
may select an imported package by its name and version or pin its snapshot ID.
Native imports validate storage, graph references and selected interfaces.
They report verification status `unchecked`.

`build_package` accepts `target: "linux-x86_64"` and selects `linux_x86_64`
bindings before portable bindings with `platform: ""`. Native interface calls
retain their interface revision, version, and required contract. The server
resolves the implementation for the build target and records the selected
callee and binding context in the build's transient graph. A missing variant
for a required interface produces `MissingImplementation`. The compiler emits
only the functions reachable from the selected public bindings. For native
programs, the bound interface `<package>.main` selects an executable with
`main() -> ExitStatus` or `main(args: LaunchArgs) -> ExitStatus`. Launch
arguments retain their original Unix bytes. The native backend covers the
built-in library, native syscall package, and native examples. Supported
interface-only packages produce a Rust `rlib`.

Compiler built-ins use the `builtin__` prefix. The server returns
`ValidationFailed` for a direct reference outside the [`builtin` package](../builtin/README.md).
It checks every function body in the package and its dependencies, including
unbound implementations. The rule also covers scalar `fail` statements,
which are the canonical form of `builtin__fail`. Packages call the exported
`builtin` interfaces through bindings.

The compiler writes its Rust translation unit in a temporary directory and
removes the directory when compilation ends. Executables and libraries go
under `<state-dir>/artifacts/`. Package directories are read-only during
import and build.

The checked-in packages use repository profile `llmlang.spg.tables.v6`. Start
with a fresh state directory and reimport dependencies before their consumers
when switching a server from the v5 examples to the v6 examples. The package
versions still identify the same releases and v6 packages have new snapshot IDs.

The native backend collects built-in calls while lowering reachable functions.
A parameterless entry point reaching `builtin__syscall` can use a Linux
`_start` and `exit_group` when the reachable code needs no Rust `std`.
Programs using `LaunchArgs` or built-ins backed by `std` use the Rust entry
point. The Linux entry point sets `SIGPIPE` to ignored so writes to closed
pipes return `EPIPE`.

For executables, `build_package` returns `debug_artifact` alongside
`artifact`. The stripped ELF uses `.gnu_debuglink` to find the adjacent
debug file. Set `OBJCOPY` to select another executable providing GNU
`objcopy` options. The native integration test also uses `readelf`.

## Verification

```sh
cargo test --locked --manifest-path draft/server/Cargo.toml
python3 -B -m unittest draft.server.scalar_verification.test_counterexamples
python3 -B draft/server/tests/mcp_e2e.py draft/server/target/debug/llmlang-server
python3 -B draft/server/tests/native_build_e2e.py draft/server/target/debug/llmlang-server
```

The end-to-end tests run the bundled Python client against the server process.
The scalar test uses Boogie and Z3 to verify edits in an in-memory workspace.
The native test imports packages, builds artifacts, and executes the binaries.
