# LLMLang SPG persistence

The Rust crate root is [src/library/spg.rs](../src/library/spg.rs).

This crate implements the repository persistence layer in the
[architecture RFC] and [ADR-030], using the twelve tables from [ADR-029].
The API works with table rows represented by JSON objects. The caller supplies
each row's logical key, including a stable composite key where applicable.
The Toolchain owns typed row interpretation, semantic identities, reference
validation, and resolution of pinned package dependencies. The manifest
preserves those dependency pins as strings.

```rust
use llmlang_spg::{load, save, LoadOptions, Manifest, Package, SaveOptions};
use std::path::Path;

fn round_trip(path: &Path) -> llmlang_spg::Result<Package> {
    let package = Package::empty(Manifest {
        language_version: "0.1.0".into(),
        dependencies: Default::default(),
    });
    save(path, &package, SaveOptions::default())?;
    load(path, &["0.1.0"], LoadOptions::default())
}
```

`save` creates a new package directory under an existing parent.
`load` takes the exact SemVer versions supported by the caller. Both default to
binary-only operation. Set `write_text_dump` to emit one JSON array of ProtoJSON
messages per table. On load also set `text_dump_dir` to a new directory outside
the package. Load publishes that export only after validating the entire input.

`load_record` reads one indexed frame by Content Hash. It can use a caller-supplied
cache of decoded rows and rechecks cached content against the requested hash
before using it. `rebuild_index` validates the entire table dump and then replaces
its index. Rebuild explicitly before retrying a load that failed because its index
was missing or invalid.

## Repository profile

The draft specifies the storage contract and leaves the physical encoding to a
profile. This crate defines `llmlang.spg.tables.v1`.

- `manifest.json` contains `profile`, `language_version`, and `dependencies`.
- Each of the twelve tables has a lowercase `<table>.dump` and
  `<table>.index.json`, even when empty. The index is a JSON object mapping
  lowercase SHA-256 hex digests to zero-based offsets at the start of a frame.
  Index keys are sorted and the compact encoding ends in a newline.
- Each dump starts with `LLSPG\x01\r\n`. Frames follow in ascending row key order.
  Each comprises a little-endian 32-bit compressed length, a little-endian
  32-bit uncompressed length, a 32-byte Content Hash, and a raw LZ4 block.
  The writer uses LZ4 fast mode with acceleration 1. The uncompressed size limit
  is 1 MiB per record and the metadata size limit is 16 MiB per file.
- Each block carries the same Protobuf wire message as
  [the syscall storage schema](../packages/linux.syscalls/storage.proto).
  Values support null, bool, signed 64-bit integers, strings, lists, and objects.
  Object fields are sorted by UTF-8 key. Record values allow nesting depth 24.
- Content Hash is SHA-256 over the bytes `llmlang-spg-content/v1\0` followed by
  compact UTF-8 JSON for the record's `content` and `key`, with object keys sorted
  recursively. It is independent of framing and compression.
- Optional `<table>.json` files contain ProtoJSON messages in frame order.
  They are never read as package inputs.

The profile reuses the syscall record schema and framing. Its package manifest,
file names, and index encoding define a separate package format. The directory
publication implementation is tested on Linux.

Run `cargo test --locked --manifest-path library/Cargo.toml` from the repository root.

[architecture RFC]: https://github.com/aivibeflow/LLMLang/blob/main/draft/RFC.md
[ADR-029]: https://github.com/aivibeflow/LLMLang/blob/main/draft/adr/029-caller-scoped-verification-obligations.md
[ADR-030]: https://github.com/aivibeflow/LLMLang/blob/main/draft/adr/030-per-table-package-dumps.md
