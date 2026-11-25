# zlib release reconciliation and bounded Rust mirror rollback

[GitHub #332](https://github.com/aivibeflow/LLMLang/issues/332) · 2026-11-25

The fixture retrieves three exact upstream release archives and compares the C `adler32_z` operation with a standalone Rust realization. It separately records the release, header closure, source occurrence, projected typed body, native ELF, mirror ELF and observation scope. Each non-system source dependency emitted by the compiler matches the exact archived member before the fixture uses it.

The 1.2.13 release uses a K&R function definition. Releases 1.3.1 and 1.3.2 use a prototype definition. Clang 19.1.7 supplies a typed function body and parameter inventory. The fixture's projection ignores source locations and compiler-local AST IDs. All three releases produce one projected body identity and, in the selected native GCC build, one exact shared library digest. Their source and release material records remain distinct.

| Evidence route | Observations |
| --- | --- |
| Exact C provider in each of three releases | 212 cases per release |
| Independent Rust mirror | 212 matching cases |
| Wrong-modulus Rust control | 124 divergent cases |

Each ordinary case checks the exact whole-buffer and independently chunked checksum. The corpus spans empty, short, large and block-boundary lengths, as well as valid starting sums and the null initialization call. The Python oracle computes the closed-form weighted byte sum, independently of the upstream loops and the Rust mirror.

## Local cutover and rollback

The fixture applies an exact receipt to the original binding. It refuses the old receipt for the middle release even though the native ELF is unchanged. It leaves the most recent release unresolved if fresh observations are missing. After the preserving comparison it atomically replaces the local selected-binding record with the exact new scope. A mirror with the same ABI and a changed checksum modulus fails the comparison and leaves that selection intact. Restoring the original exact record recovers the previous release, input closure and mirror association.

The source projection covers one fixed C function, not general C semantics. Binding and rollback use a local file with a serialized writer. Repository integration, authenticated source correspondence, independent review, broader zlib APIs, live upstream participation and production cutover remain open.

## Replay

Use CPython 3.12.14, GCC 14.2.0, Clang 19.1.7 and Rust 1.85.1 on Linux x86-64. Download and extract the official GitHub tag archives for [v1.2.13](https://codeload.github.com/madler/zlib/tar.gz/refs/tags/v1.2.13), [v1.3.1](https://codeload.github.com/madler/zlib/tar.gz/refs/tags/v1.3.1) and [v1.3.2](https://codeload.github.com/madler/zlib/tar.gz/refs/tags/v1.3.2), retaining each archive as `zlib-VERSION.tar.gz` beside its extracted directory. The runner checks their SHA-256 pins.

```sh
fixture=research/compiler-and-translation/RT-28/ZLIB-RELEASE-MIRROR-01
python "$fixture/run.py" --clang /path/to/clang19 --inputs /path/to/zlib-archives \
  --output /tmp/rt28-zlib-mirror.json
cmp "$fixture/evidence.json" /tmp/rt28-zlib-mirror.json
```

Two clean builds produced identical [evidence ledgers](ZLIB-RELEASE-MIRROR-01/evidence.json).
