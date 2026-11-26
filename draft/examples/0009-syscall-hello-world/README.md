# 0009 — Hello, World! using a syscall

[`main.llmlang`](main.llmlang) calls `stdlib.syscall` with Linux x86-64
syscall number 1 (`write`). It passes file descriptor 1, the address and length
of the remaining UTF-8 bytes, and zeros for the three unused argument words.
It retries interrupted writes, advances after short writes, and returns 1
if output fails.

Import `draft/stdlib` version `0.1.0` through MCP, then import this package
and build it for `linux-x86_64`. The
[native MCP test](../../server/tests/native_build_e2e.py) checks the exact
output `Hello, world!\n`, exit status zero, empty stderr, and failure
with stdout redirected to `/dev/full`. Native builds report
verification status `unchecked`.
