# Reproducible incremental translation and partitioned replay

[GitHub #327](https://github.com/aivibeflow/LLMLang/issues/327) · 2026-11-25

The fixture separates release object identity, linked artifact identity, debug objects and verification receipts. Root A calls a separately compiled helper. Root B is independent. The source-level oracle specifies each root's wrapping byte operation over an explicit input partition.

## Scope and keys

The release build key binds emitted C, compiler options and recorded toolchain binaries. Linking binds the ordered object digests and executable link options. The compiler uses a normalized build directory for DWARF. Each debug object instead binds its source-location input and is checked through decoded line output. The verification key binds the root, release library digest, exact input interval, contract rule, oracle revision, fixture and toolchain. Cached failures remain failures. The runner reopens its disk index for each phase and verifies stored artifact hashes before use.

The runner compiles a real shared object for each root and checks its exported symbol and absence of required dynamic libraries. An independent Python oracle compares native calls in chunks of 128 inputs. Both roots are admitted only for their recorded partitions. The cache contains 896 fresh native checks per build root over the sequence.

| Phase | Release compilations | Links | Debug compilations | Fresh verification partitions |
| --- | ---: | ---: | ---: | ---: |
| Initial | 3 | 2 | 2 | 2 |
| Reopen the unchanged cache | 0 | 0 | 0 | 0 |
| Move A's source location | 0 | 0 | 1 | 0 |
| Extend A's contract from 128 to 256 inputs | 0 | 0 | 0 | 1 |
| Change the helper's addend without changing A's source contract | 1 | 1 | 0 | 2 |
| Restore the exact helper | 0 | 0 | 0 | 0 |
| Change A's oracle revision | 0 | 0 | 0 | 2 |

The source-location change produces a different debug object with the new filename and preserves both release artifacts. Widening the contract reuses the original low partition and checks the additional high partition. The changed helper leaves the caller object unchanged but changes A's linked library and fails all 256 required inputs. Root B's executable bytes and receipt stay reusable. Restoring the helper recovers the previous exact artifact and both receipts. Changing the oracle revision triggers two checks while retaining the executable.

Two empty cache roots with distinct work directories yield the same object bytes, executable bytes, debug bytes, scope identities and observations for every phase. The fixture records GCC driver, compiler proper, assembler and linker digests. The graph and partitions are declared inputs. The evidence covers the tested freestanding shared objects, source mapping and exact cache reuse. Production dependency discovery, authenticated receipts, parallel writers and wider target support remain open.

## Replay

Use CPython 3.12.14, GCC 14.2.0, GNU binutils 2.44 and Linux x86-64.

```sh
fixture=research/compiler-and-translation/RT-09/INCREMENTAL-TRANSLATION-CLOSURE-01
python "$fixture/run.py" --output /tmp/rt09-incremental.json
cmp "$fixture/evidence.json" /tmp/rt09-incremental.json
```

Each invocation runs the seven phases in two independent roots. Two full invocations produced identical [evidence ledgers](INCREMENTAL-TRANSLATION-CLOSURE-01/evidence.json).
