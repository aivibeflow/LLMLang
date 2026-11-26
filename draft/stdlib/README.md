# Native standard library

Import this SPG package as `stdlib` version `0.1.0` on Linux x86-64.
Applications import its functions through package bindings.

| Function | Behavior |
|---|---|
| [`write(fd: I32, utf8: Utf8) -> IoResult`](write.llmlang) | Writes the entire UTF-8 string to the supplied file descriptor. It retries interrupted writes, completes short writes, and returns `Ok(())` or `Err(errno)` with a positive Linux errno. It adds no newline and leaves the descriptor open. |
| [`unsafe fn syscall(number: Usize, arg0: Usize, …, arg5: Usize) -> AbiResult`](syscall.llmlang) | Invokes the native Linux x86-64 ABI with six words. The caller supplies zero for unused words and must meet the chosen syscall's ABI requirements. The result is the raw signed return value, including negative errno. Calls requiring a dedicated continuation return `-ENOSYS`. |

The package implements these interfaces with `builtin__write_utf8` and
`builtin__syscall`. Hello World selects the first interface, and
`linux.syscalls` selects the second. The MCP build includes the
implementations reachable from the package's selected public bindings.
