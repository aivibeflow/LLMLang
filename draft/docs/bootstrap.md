# LLMLang agent bootstrap

Start here when a task asks you to read, write, verify, or build LLMLang. Use the repository's [agent instructions](../../AGENTS.md) for checkout changes and the [architecture RFC](../RFC.md) for design questions.

## Choose the workflow

| Task | Start with |
| --- | --- |
| Write or inspect a scalar `.llmlang` source file | Read the [scalar text syntax](lang.md#scalar-text-source). Use Stage 0 `lower` to check syntax and types. Use the [scalar MVP CLI](../../tools/llmlang_mvp/README.md) for the standalone Calculator contract and build workflow. |
| Author, revise, verify, or build a package | Use the [MCP server guide](server.md) and the [structured scalar syntax](lang.md#scalar-mcp-authoring). |
| Inspect an existing package | Identify its exact snapshot. Use [MCP resource reads](server.md#tools-and-resources) to inspect identities, bindings, contracts, and links. Import the package and its dependencies if the snapshot is absent from the catalog. |
| Build a committed native syscall package | Follow the [native package example](server.md#build-an-existing-native-program). Report native import and build status as `unchecked`. |
| Work with Linux syscall guests or providers | Use the [syscall package toolchain](../../packages/linux.syscalls/README.md) and its declared profile. |

Use the executable forms in [lang.md](lang.md). The Hello, Echo, and Calculator sketches in [draft examples](../examples/README.md) illustrate candidate notation.

## Author through MCP

1. Connect to LLMLang Server and discover `tools/list` and `resources/templates/list`. If the connection is absent and you can launch local processes, use the [build and connection instructions](server.md#build-and-connect) for a local stdio session.
2. Create a package with `profile: "scalar"` and `language_version: "0.1.0"`, or open a workspace from the intended snapshot. Keep the returned `workspace_id` and `revision`. For existing work, inspect the selected version, exports, entry point, dependencies, and relevant graph objects before editing.
3. Translate the requested behavior into typed signatures, contract rules, and implementation bodies. Preserve the intended input domain, success results, and error outcomes. Create interfaces and bindings for requested exports. Select a parameterless local entry point for an executable.
4. Send the changes in `apply_change_set` with the current `expected_revision` and a fresh idempotency key. Use the server's existing identities or same-batch local references. Pin both the callee implementation and its required contract in each call. Use object content hashes as edit preconditions and update call pins explicitly where the requested behavior changes them.
5. Call `verify_workspace` for the resulting revision. Read the obligations and diagnostics when `report.report.status` differs from `VERIFIED`. A successful apply establishes that the candidate passed structural and type validation. A verified preview supplies evidence for that revision under the scalar policy.
6. When the task calls for publication, commit that revision and record the returned snapshot ID and package path. When it calls for a native artifact, build that snapshot for `linux-x86_64` and record the artifact path. Run an executable when the task requires checking its process behavior.

For a concrete first request, follow the [executable example](server.md#create-an-executable). For a stale revision, lost response, or verification failure, follow the [recovery instructions](server.md#recover-from-a-conflict-or-interrupted-request).

Report the scope of the observed result. For source work, report which frontend or checks ran. For MCP work, include the workspace revision, verification status, and any snapshot ID or artifact produced. Surface diagnostics that still prevent the requested outcome.
