# LLMLang Server MVP

This Linux server implements scalar package authoring over MCP stdio. Run a
server per local OS principal with an owner-private state directory. Its
Toolchain operations are also available through the Rust `Server` API.
The service serializes operations within one process and holds an exclusive
lock on the state directory. A local MCP client uses the authority of the
process that launches it.

The Rust sources are in [draft/src/server](../src/server).

## Build and run

Use Rust 1.85.1 or newer, Python 3.10 or newer, Boogie with its .NET runtime,
and Z3. The native build target is Linux x86-64. Run the following from the
repository root.

```sh
cargo build --locked --manifest-path tools/llmlang_mvp/stage0/Cargo.toml
cargo build --locked --manifest-path draft/server/Cargo.toml

export LLMLANG_STAGE0="$PWD/tools/llmlang_mvp/stage0/target/debug/llmlang-stage0"
export BOOGIE=/path/to/boogie
export Z3=/path/to/z3

draft/server/target/debug/llmlang-server --state-dir /path/to/private-state
```

Configure the MCP client to launch that last command. The server creates its
state directory if it is missing. It accepts `--python` and `--backend`
overrides for the trusted scalar toolchain. Its default backend is
[scalar.py](scalar.py). The MCP stream uses one JSON-RPC message per line.

## Package lifecycle

Use `tools/list` to discover the input and output schemas. Start with
`create_package` using `profile: "scalar"` and `language_version: "0.1.0"`.
With `apply_change_set`, select a package version and submit structured
contracts, implementations, interfaces, and bindings. A batch can refer to a
new object with `{"local":"its_request_id"}`. Use
`resources/templates/list` and `resources/read` to inspect a function, its
Content Hash, and its dependency links. For a complete example request, see
[the MCP integration test](tests/mcp_e2e.py).

`apply_change_set` validates the candidate before persisting a new revision.
`verify_workspace` produces a preview. `commit_workspace` runs verification
for the supplied revision, writes the package, and returns the committed
snapshot ID and package path. It enables per-table debug ProtoJSON. Committed
version directories are immutable. The configured destination is
`<state-dir>/packages/<package-name>/<version>`.

The package contains the standard SPG manifest, table dumps and indexes, plus
`package.json` with the package name, version selection, optional entry point,
and snapshot ID used by this server. Import verifies the package, reconstructs
its identity, and registers the snapshot. Import pinned dependencies before
importing a package that uses them. Dependency pins are exact snapshot IDs.

`build_package` accepts `target: "linux-x86_64"`. A package with a
parameterless scalar entry point produces an executable that prints its
result. An interface-only package produces a Rust `rlib` and reports the
exported Rust symbol names. The first profile uses a fixed admission policy
that requires successful scalar verification.

## Verification

```sh
cargo test --locked --manifest-path draft/server/Cargo.toml
python3 -B draft/server/tests/mcp_e2e.py draft/server/target/debug/llmlang-server
```

The end-to-end test starts independent MCP client and server processes. It
requires the real Boogie, Z3, and native build tools. It verifies commits,
imports packages into fresh state, and executes the resulting binary.
