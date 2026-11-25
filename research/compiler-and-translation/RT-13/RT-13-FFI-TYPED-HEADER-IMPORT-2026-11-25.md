# Bounded C header import for POSIX, SQLite and OpenSSL

[GitHub #329](https://github.com/aivibeflow/LLMLang/issues/329) · 2026-11-25

The importer reads the Clang AST for actual development headers and maps three C declarations to a small typed FFI profile. The Linux x86-64 LP64 fixture admits fixed-width integers, size types and qualified pointers to primitive or opaque types. It extracts the underlying size and opaque aliases and checks pointer width, integer width and endianness. It emits C function-pointer declarations and uses compiler type compatibility checks against the included headers.

| Imported symbol | Independently supplied adapter obligation | Observations per build |
| --- | --- | ---: |
| POSIX `read` | Check buffer capacity before the call. Capture `errno` on failure and preserve the exact returned byte prefix. | 56 |
| SQLite `sqlite3_stricmp` | Require NUL-terminated strings and compare the sign under ASCII folding. | 144 |
| OpenSSL `EVP_Digest` | Select SHA-256 explicitly and check the returned 32-byte digest. Keep the input and output buffers live. | 27 |

The contracts and adapter implementations are separate from the parsed signature inventory. The declaration shape identifies types, while a reviewed behavior record supplies length, lifetime and result rules. The native driver links the libraries, records the exact symbol providers with `dladdr` and pins their binary digests. The SHA-256 oracle uses CPython's `_sha2` implementation. It compares digest bytes independently of the OpenSSL provider used by the executable. [POSIX read](https://pubs.opengroup.org/onlinepubs/9699919799/functions/read.html) · [SQLite comparison](https://www.sqlite.org/c3ref/stricmp.html) · [OpenSSL digest](https://docs.openssl.org/3.5/man3/EVP_DigestInit/)

The O0 and O2 builds agree on all 454 positive observations and have the same observation digest. Replacing the imported `size_t` read parameter with `unsigned int` fails the compile-time signature check. An ABI-identical control selects SHA-512, still links the exact same provider libraries, and differs on all 27 digest rows. Width and behavioral scope have independent evidence.

The fixture covers exact named imports in glibc 2.41, SQLite 3.46.1 and OpenSSL 3.5.7 on the recorded host. General C or IDL parsing, language-specific ABI generation, other operating-system APIs, OpenSSL provider configuration, authenticated contracts and production admission remain open.

## Replay

Use CPython 3.12.14 with `_sha2`, Clang 19.1.7, GCC 14.2.0 and the libraries above. The Debian SQLite development package `libsqlite3-dev_3.46.1-7+deb13u2_amd64.deb` was extracted without modifying the system. Its SHA-256 is `56e1945d52292b506c1f0bcb77543fea289ccee857c478dcddded40226e1594d`. The runner records selected header and provider digests.

```sh
fixture=research/compiler-and-translation/RT-13/FFI-TYPED-HEADER-IMPORT-01
python "$fixture/run.py" --clang /path/to/clang19 --sqlite-headers /path/to/usr/include \
  --output /tmp/rt13-ffi-import.json
cmp "$fixture/evidence.json" /tmp/rt13-ffi-import.json
```

Two native builds from independent temporary roots reproduced the [evidence ledger](FFI-TYPED-HEADER-IMPORT-01/evidence.json).
