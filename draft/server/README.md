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

`build_package` accepts `target: "linux-x86_64"`. The server starts from
the selected public bindings and emits the functions reachable through exact
call pins, including required implementations from dependencies. For native
programs, the bound interface `<package>.main` selects an executable with
`main() -> ExitStatus` or `main(args: LaunchArgs) -> ExitStatus`. Launch
arguments retain their original Unix bytes. The native backend covers the
standard library package, Hello World, the native syscall package, and the
five draft syscall programs. Supported
interface-only packages produce a Rust `rlib`.

Compiler built-ins use the `builtin__` prefix. The server returns
`ValidationFailed` for a direct reference outside [stdlib](../stdlib/README.md).
It checks every function body in the package and its dependencies, including
unbound implementations. The rule also covers scalar `fail` statements,
which are the canonical form of `builtin__fail`. Other packages can use
operations backed by built-ins through public `stdlib` interfaces.

The compiler writes its Rust translation unit in a temporary directory and
removes the directory when compilation ends. Executables and libraries go
under `<state-dir>/artifacts/`. Package directories are read-only during
import and build.

## Verification

```sh
cargo test --locked --manifest-path draft/server/Cargo.toml
python3 -B draft/server/tests/mcp_e2e.py draft/server/target/debug/llmlang-server
python3 -B draft/server/tests/native_build_e2e.py draft/server/target/debug/llmlang-server
```

The end-to-end test starts independent MCP client and server processes. It
requires the real Boogie, Z3, and native build tools. It verifies scalar edits and their in-memory lifetime. The native test imports packages and executes the binaries.
