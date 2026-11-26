# Candidate Example Implementations

This directory contains candidate LLMLang implementations corresponding to task statements in `/examples/`.

**Important status:** LLMLang's concrete syntax and executable toolchain are not yet established sufficiently to claim these files compile. The `.llmlang` files are deliberately written as readable semantic/DSL sketches using concepts from the current research. They are implementation candidates, not validated executable programs.

## Rules

- Each solution directory has the same task ID and slug as its task statement.
- The task statement in `/examples/` is authoritative. Implementations must not weaken or redefine its requirements.
- Keep implementation-specific decisions here; promote any externally observable behavior change to the task statement first.
- Include a requirement-to-code mapping and test status.
- Do not label a solution compiled, tested, or verified unless the corresponding tool actually ran and produced evidence.

## Native package example

[linux.syscalls](linux.syscalls/README.md) contains a native Linux x86-64
package in the current SPG repository format.

## Linux syscall program packages

Each program has a public `main` interface bound to its implementation in the
package's selected version. Copy takes `LaunchArgs`. The other four programs
have a parameterless `main`. All return `ExitStatus`.

| Package | Scenario | Reference fixture |
|---|---|---|
| [0004-syscall-echo](0004-syscall-echo/main.llmlang) | Copy standard input to standard output, including short writes and interrupted calls. | [Echo](../../packages/linux.syscalls/examples/echo.llmlang) |
| [0005-syscall-copy](0005-syscall-copy/main.llmlang) | Copy a file to a new path, close both descriptors, and report I/O errors. | [Copy](../../packages/linux.syscalls/examples/copy.llmlang) |
| [0006-syscall-pipe-poll](0006-syscall-pipe-poll/main.llmlang) | Check pipe readiness before and after writing a byte. | [Pipe readiness](../../packages/linux.syscalls/examples/pipe_poll.llmlang) |
| [0007-syscall-child](0007-syscall-child/main.llmlang) | Launch a child, wait for it, and return the child's exit status. | [Child](../../packages/linux.syscalls/examples/child.llmlang) |
| [0008-syscall-tcp-echo](0008-syscall-tcp-echo/main.llmlang) | Exchange a byte-exact payload on IPv4 loopback. | [TCP Echo](../../packages/linux.syscalls/examples/tcp_echo.llmlang) |

The manifest of each program selects version `v6.12` of `linux.syscalls`.
A caller of the SPG graph loader registers the dependency graph for that
version under `v6.12`. A native function body contains only its source block.
The server recovers the entry signature through the function's signature-table reference.
It checks the caller, callee, and required contract in each call
compatibility obligation against the block and selected dependency bindings. Their binary and ProtoJSON dumps include all thirteen tables.

The [native MCP build test](../server/tests/native_build_e2e.py) imports and
builds these packages on Linux x86-64, then executes all five programs. Build
artifacts are stored in server state. The linked reference fixtures continue to
provide inputs to the [Stage 0 test runner](../../packages/linux.syscalls/examples/check.py).
