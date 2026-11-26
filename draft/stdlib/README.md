# Native standard library

Import this SPG package as `stdlib` version `0.1.0` on Linux x86-64.
Applications import its functions through package bindings.

| Function | Behavior |
|---|---|
| [`write(fd: I32, utf8: Utf8) -> IoResult`](write.llmlang) | Writes the entire UTF-8 string to the supplied file descriptor. It retries interrupted writes, completes short writes, and returns `Ok(())` or `Err(errno)` with a positive Linux errno. It adds no newline and leaves the descriptor open. |
| [`unsafe fn syscall(number: Usize, arg0: Usize, …, arg5: Usize) -> AbiResult`](syscall.llmlang) | Invokes the native Linux x86-64 ABI with six words. The caller supplies zero for unused words and must meet the chosen syscall's ABI requirements. The result is the raw signed return value, including negative errno. Calls requiring a dedicated continuation return `-ENOSYS`. |
| [`errno_message(errno: AbiResult) -> ByteVec`](errno_message.llmlang) | Formats a positive Linux errno as diagnostic bytes with a trailing line feed. |
| [`cstring_from_bytes(bytes: ByteSlice) -> CStringResult`](cstring_from_bytes.llmlang) | Copies bytes into a NUL-terminated C string or returns an error for an embedded NUL. |
| [`trap() -> Never`](trap.llmlang) | Aborts the process. |
| [`sockaddr_in_loopback(port: U16) -> sockaddr_in`](sockaddr_in_loopback.llmlang) | Constructs a Linux IPv4 loopback address with a port supplied in host byte order. |
| [`sockaddr_in_size() -> Usize`](sockaddr_in_size.llmlang) | Returns the size of `sockaddr_in` for the native ABI. |

The package implements these interfaces with native built-ins. The MCP build includes the
implementations reachable from the package's selected public bindings.
