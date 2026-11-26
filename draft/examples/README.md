# Candidate Example Implementations

This directory contains candidate LLMLang implementations corresponding to task statements in `/examples/`.

The packages below build and run through the native MCP server. The Echo and
Calculator sketches in `0002-echo` and `0003-calculator` remain illustrative.

## Rules

- Each solution directory has the same task ID and slug as its task statement.
- The task statement in `/examples/` is authoritative. Implementations must not weaken or redefine its requirements.
- Keep implementation-specific decisions here; promote any externally observable behavior change to the task statement first.
- Include a requirement-to-code mapping and test status.
- Do not label a solution compiled, tested, or verified unless the corresponding tool actually ran and produced evidence.

## Native package example

[0001-hello-world](0001-hello-world/README.md) writes its greeting through
[`stdlib.write`](../stdlib/README.md). Import `draft/stdlib` before importing
either Hello World package or the Linux syscall package.
[0009-syscall-hello-world](0009-syscall-hello-world/README.md) writes the same
greeting through `stdlib.syscall` using the Linux x86-64 `write` ABI.

[linux.syscalls](linux.syscalls/README.md) contains a native Linux x86-64
package in the current SPG repository format.

## Linux syscall program packages

Each program has a public `main` interface bound to its implementation in the
package's selected version. Copy takes `LaunchArgs`. The other four programs
have a parameterless `main`. All return `ExitStatus`.

| Package | Scenario |
|---|---|
| [0004-syscall-echo](0004-syscall-echo/main.llmlang) | Copy standard input to standard output, including short writes and interrupted calls. |
| [0005-syscall-copy](0005-syscall-copy/main.llmlang) | Copy a file to a new path, close both descriptors, and report I/O errors. |
| [0006-syscall-pipe-poll](0006-syscall-pipe-poll/main.llmlang) | Check pipe readiness before and after writing a byte. |
| [0007-syscall-child](0007-syscall-child/main.llmlang) | Launch a child, wait for it, and return the child's exit status. |
| [0008-syscall-tcp-echo](0008-syscall-tcp-echo/main.llmlang) | Exchange a byte-exact payload on IPv4 loopback. |

The manifest of each program selects version `v6.12` of `linux.syscalls`.
A caller of the SPG graph loader registers the dependency graph for that
version under `v6.12`. A native function body contains only its source block.
The server recovers the entry signature through the function's signature-table reference.
It checks the caller, callee, and required contract in each call
compatibility obligation against the block and selected dependency bindings. Their binary and ProtoJSON dumps include all thirteen tables.

The [native MCP build test](../server/tests/native_build_e2e.py) imports and
builds these packages on Linux x86-64, then runs both Hello World examples and eleven
scenarios across the five syscall programs. The scenarios check exit status, binary I/O, Linux error diagnostics,
and partial file contents after a write failure. Build artifacts are stored in
server state.
