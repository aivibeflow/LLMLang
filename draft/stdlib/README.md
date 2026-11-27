# Native standard library

On Linux x86-64, import [`builtin` version `0.1.0`](../builtin/README.md), then import this SPG package as `stdlib` version `0.1.0`.
Applications import its functions through package bindings.

Function bodies appear as `canonicalBody` in [`functions.json`](functions.json).
Their signatures are in [`function_signatures.json`](function_signatures.json).

| Function | Behavior |
|---|---|
| `write(fd: I32, utf8: Utf8) -> IoResult` | Writes the entire UTF-8 string to the supplied file descriptor. It retries interrupted writes, completes short writes, and returns `Ok(())` or `Err(errno)` with a positive Linux errno. It adds no newline and leaves the descriptor open. |
| `unsafe fn syscall(number: Usize, arg0: Usize, …, arg5: Usize) -> AbiResult` | Invokes the native Linux x86-64 ABI with six words. The caller supplies zero for unused words and must meet the chosen syscall's ABI requirements. The result is the raw signed return value, including negative errno. Calls requiring a dedicated continuation return `-ENOSYS`. |
| `errno_message(errno: AbiResult) -> ByteVec` | Formats a positive Linux errno as diagnostic bytes with a trailing line feed. |
| `cstring_from_bytes(bytes: ByteSlice) -> CStringResult` | Copies bytes into a NUL-terminated C string or returns an error for an embedded NUL. |
| `trap() -> Never` | Aborts the process. |
| `sockaddr_in_loopback(port: U16) -> sockaddr_in` | Constructs a Linux IPv4 loopback address with a port supplied in host byte order. |
| `sockaddr_in_size() -> Usize` | Returns the size of `sockaddr_in` for the native ABI. |

These interfaces forward to [`builtin`](../builtin/README.md) through exact
implementation and contract pins. The MCP build includes the implementations
reachable from the package's selected public bindings.
