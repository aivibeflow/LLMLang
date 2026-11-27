# 0009 — Hello, World! using a syscall

The body in [`functions.json`](functions.json) calls `linux.syscalls.write` with file
descriptor 1, the remaining bytes, and their length. It retries interrupted
writes, advances after short writes, and returns 1 if output fails.

Through MCP, import `draft/builtin` version `0.1.0`, then
`draft/examples/linux.syscalls` version `v6.12`. Import this package and build it for
`linux-x86_64`. The
[native MCP test](../../server/tests/native_build_e2e.py) checks the exact
output `Hello, world!\n`, exit status zero, empty stderr, and failure
with stdout redirected to `/dev/full`. Native builds report
verification status `unchecked`.
