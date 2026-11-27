# Built-in library

This native Linux x86-64 SPG package is `builtin` version `0.1.0`. It is
the package allowed to reference compiler primitives whose names start with
`builtin__`. [ADR-034](../adr/034-built-in-function-prefix.md)

Function bodies appear as `canonicalBody` in [`functions.json`](functions.json).
Their signatures are in [`function_signatures.json`](function_signatures.json).

| Interface | Compiler primitive |
| --- | --- |
| `builtin.syscall` | `builtin__syscall` |
| `builtin.write` | `builtin__write_utf8` |
| `builtin.errno_message` | `builtin__errno_message` |
| `builtin.cstring_from_bytes` | `builtin__cstring_from_bytes` |
| `builtin.trap` | `builtin__trap` |
| `builtin.sockaddr_in_loopback` | `builtin__sockaddr_in_loopback` |
| `builtin.sockaddr_in_size` | `builtin__size_of` specialized to `sockaddr_in` |

Import this package before [`stdlib`](../stdlib/README.md). The standard
library pins these implementations and contracts through its forwarding
wrappers. Use a fresh server state directory when importing these fixtures
over an earlier checkout's package set. The fixture versions are the same,
and their snapshot identities reflect the new call pins.
