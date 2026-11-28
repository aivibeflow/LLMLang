# Built-in library

This native Linux x86-64 SPG package is `builtin` version `0.1.0`. It is
the package allowed to reference compiler primitives whose names start with
`builtin__`. [ADR-034](../adr/034-built-in-function-prefix.md)

Function bodies appear as `canonicalBody` in [`functions.json`](functions.json).
Their signatures are in [`function_signatures.json`](function_signatures.json).

| Interface | Compiler primitive | Behavior |
| --- | --- | --- |
| `builtin.syscall` | `builtin__syscall` | Invokes the native Linux x86-64 ABI with six words. The caller supplies zero for unused words and must meet the chosen syscall's ABI requirements. The result is the raw signed return value, including negative errno. Calls requiring a dedicated continuation return `-ENOSYS`. |
| `builtin.write` | `builtin__write_utf8` | Writes the entire UTF-8 string to the supplied file descriptor. It retries interrupted writes, completes short writes, and returns `Ok(())` or `Err(errno)` with a positive Linux errno. It adds no newline and leaves the descriptor open. |
| `builtin.errno_message` | `builtin__errno_message` | Formats a positive Linux errno as diagnostic bytes with a trailing line feed. |
| `builtin.cstring_from_bytes` | `builtin__cstring_from_bytes` | Copies bytes into a NUL-terminated C string or returns an error for an embedded NUL. |
| `builtin.trap` | `builtin__trap` | Aborts the process. |
| `builtin.sockaddr_in_loopback` | `builtin__sockaddr_in_loopback` | Constructs a Linux IPv4 loopback address with a port supplied in host byte order. |
| `builtin.sockaddr_in_size` | `builtin__size_of` specialized to `sockaddr_in` | Returns the size of `sockaddr_in` for the native ABI. |

The raw `builtin.syscall` binding specifies `arch: "x86_64", os: "linux"`. The other
interfaces have portable bindings. Import this package before its consumers.
Use the MCP supervisor to migrate an existing server state to repository profile v9.
