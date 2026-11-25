# Static allocator selection across Rust and C ownership scopes

[GitHub #332](https://github.com/aivibeflow/LLMLang/issues/332) · 2026-11-25

The fixture builds exact mimalloc archives with and without public symbol overrides. It compares the platform Rust allocator with a named `GlobalAlloc` implementation and an executable-linked public override. Each executable also exercises two explicitly selected component heaps. Glibc remains dynamically linked in each configuration.

| Configuration | Rust allocation observed in mimalloc region | Direct public C allocation observed in mimalloc region | Exported `malloc` provider |
| --- | --- | --- | --- |
| Rust System with named components | No | No | glibc |
| Named Rust global allocator with named components | Yes | No | glibc |
| Executable-linked public override with named components | Yes | Yes | Main executable |

The runner observes the public allocation symbol's image base and checks the allocator's own region and heap queries. It retains exact archive and ELF digests. The broad process override evidence covers the fixture's directly observed public calls. It leaves hidden allocation entry points inside other native libraries outside the checked scope.

## Allocation and release observations

The 3.7.1 profiles each check 36 size and alignment combinations, or 108 combined rows. The largest alignment is 4,096 bytes. Rust verifies zero initialization and preserved prefixes through reallocation. C allocation preserves the expected bytes. The explicit component reallocation and release preserve the exact owner. All 108 wrong-component release attempts return a refusal before freeing. The source oracle computes a separate checksum for every initialized block.

The legacy 2.0.9 static profile reports an alignment failure for a 1,024-byte component allocation requesting 256-byte alignment. The probe checks the returned address before reading or writing the block. This is a scoped refusal for the tested old provider and build. The preserving profiles use a separately built 3.7.1 archive. Its component ownership query differs from the older version's API and is selected from the actual development header.

The experiment separates per-executable policy, Rust-only global allocation, public C interposition and explicit component ownership. It provides correctness and link-closure evidence on one Linux configuration. It leaves other libc and OS combinations, concurrency through isolated component heaps, representative workloads, tail latency, allocator selection and handling of unobserved native calls open. [Allocator exit criteria](RT-25-MEMORY-ALLOCATOR-COMPATIBILITY-AND-BENCHMARKING.md)

## Replay

Use Rust 1.85.1, GCC 14.2.0, CPython 3.12.14, CMake 3.31.6 and glibc 2.41. The Debian original source archives have the following digests.

| Archive | SHA-256 |
| --- | --- |
| `mimalloc_3.7.1+ds.orig.tar.xz` | `9d1f2207959e4485bf9035b76ad2f958c861d5f5ae9074a82a4e22720939ecba` |
| `mimalloc_2.0.9+ds.orig.tar.xz` | `cbc9d207ff105ad1f0cb739c378076143a6452b8d0624309cea0abfb040e972b` |

```sh
fixture=research/runtime-and-systems/RT-25/STATIC-ALLOCATOR-SELECTION-01
python "$fixture/run.py" --mimalloc-source /path/to/mimalloc-3.7.1 \
  --legacy-source /path/to/mimalloc-2.0.9 --output /tmp/rt25-static-allocator.json
cmp "$fixture/evidence.json" /tmp/rt25-static-allocator.json
```

Two full replays from separate build roots produced identical [evidence ledgers](STATIC-ALLOCATOR-SELECTION-01/evidence.json).
