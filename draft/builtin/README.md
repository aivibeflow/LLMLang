# Built-in library

This native Linux x86-64 SPG package is `builtin` version `0.1.0`. It is
the package allowed to reference compiler primitives whose names start with
`builtin__`. [ADR-034](../adr/034-built-in-function-prefix.md)

| Interface | Compiler primitive |
| --- | --- |
| [`builtin.syscall`](syscall.llmlang) | `builtin__syscall` |
| [`builtin.write`](write.llmlang) | `builtin__write_utf8` |
| [`builtin.errno_message`](errno_message.llmlang) | `builtin__errno_message` |
| [`builtin.cstring_from_bytes`](cstring_from_bytes.llmlang) | `builtin__cstring_from_bytes` |
| [`builtin.trap`](trap.llmlang) | `builtin__trap` |
| [`builtin.sockaddr_in_loopback`](sockaddr_in_loopback.llmlang) | `builtin__sockaddr_in_loopback` |
| [`builtin.sockaddr_in_size`](sockaddr_in_size.llmlang) | `builtin__size_of` specialized to `sockaddr_in` |

Import this package before [`stdlib`](../stdlib/README.md). The standard
library pins these implementations and contracts through its forwarding
wrappers. Use a fresh server state directory when importing these fixtures
over an earlier checkout's package set. The fixture versions are the same,
and their snapshot identities reflect the new call pins.
