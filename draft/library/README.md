# LLMLang SPG persistence

This crate implements the repository persistence layer in the
[architecture RFC] and [ADR-030], including the signature table from [ADR-033].
The API accepts JSON objects with the columns declared for their table. Each
map key must match the row's primary-key columns, joined with `:` for a
composite key. The binary record contains only the table columns.
The Toolchain owns semantic identity calculation and verification, and supplies
verified graphs for pinned package dependencies.

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

## Resolved graph

The Rust crate root is [draft/src/library/spg.rs](../src/library/spg.rs).
Use `load_graph` to decode typed rows and resolve their references. Look up a
node by its table and primary key with `Graph::get`. Follow `Node::outgoing`,
`Node::incoming`, or `Node::calls` to traverse resolved nodes. Canonical IR is
preserved as JSON. In that IR, `struct_impl_hash` is a structure pin and
`callee_impl_hash` with `required_contract_hash` is an exact call pin pair.

Supply the previous graph in `GraphLoadOptions::previous` when loading another
snapshot. A matching table and Content Hash shares the immutable object and
skips the frame read and decode. An index remains required, and a fully cached
nonempty table needs no dump access. Previous rows that the new indexes do not
select are omitted. Declared dependencies participate in reference resolution
through the caller-supplied map of exact pins to verified graphs. A missing or
ambiguous target fails the load.

Use `load` for raw package inspection, per-table ProtoJSON output, or full
validation of on-disk frames independently of the graph cache.

## Function signatures

Stage a typed signature with `Package::stage_function_signature` before
writing its function row. The row stores `function_signature_hash` and
body-only `canonical_body`. `Package::function_signature` reconstructs the
original typed signature. A graph function links to its signature row, and
the signature row links to its exact structure revisions when applicable.
Function contracts retain their typed signatures.

The v4 signature text has the form `<profile> (<name>: <type>, ...) -> <type>`.
For example, the scalar signature for one integer parameter is
`scalar-v1 (value: I64) -> I64`. The scalar profile renders `i64` and `bool`
as `I64` and `Bool`. Parameter order is preserved, spacing is fixed, and
structured type descriptors use compact JSON with recursively sorted keys.
A type name that cannot use the bare syntax is quoted as a JSON string.
The signature hash consists of `sha256:` and the lowercase SHA-256 hex digest
of `llmlang-function-signature/v1\0`, the profile, a NUL byte, and the UTF-8
signature text, in that order.

The checked-in native packages were converted from v3 with their original
reader. Their recovered typed signatures, implementation identities and
bindings match the v3 records. A v4 server starts with v4 package data.

## Repository profile

The draft specifies the storage contract and leaves the physical encoding to a
profile. This crate uses `llmlang.spg.tables.v4`.

- `manifest.json` contains `profile`, `language_version`, and `dependencies`.
- Each of the thirteen tables has a lowercase `<table>.dump` and
  `<table>.index.json`, even when empty. The index is a JSON object mapping
  lowercase SHA-256 hex digests to zero-based offsets at the start of a frame.
  Index keys are sorted and the compact encoding ends in a newline.
- Each dump starts with `LLSPG\x04\r\n`. Frames follow in ascending row key order.
  Each comprises a little-endian 32-bit compressed length, a little-endian
  32-bit uncompressed length, a 32-byte Content Hash, and a raw LZ4 block.
  The writer uses LZ4 fast mode with acceleration 1. The uncompressed size limit
  is 1 MiB per record and the metadata size limit is 16 MiB per file.
- Each block carries the table's own message from the
  [SPG Protobuf schema](proto/spg.proto), such as `FunctionRecord` for
  `functions.dump` and `VersionRecord` for `versions.dump`. Cargo generates
  these Rust types with Prost and a bundled `protoc`. Columns have explicit
  field numbers, and nested IR and review payloads use a shared recursive
  `Value` message. It supports null, bool, signed 64-bit integers, strings,
  lists, and objects with sorted UTF-8 keys. Nesting depth is limited to 24.
- Content Hash is SHA-256 over the bytes `llmlang-spg-content/v1\0` followed by
  compact UTF-8 JSON for the record's `content` and `key`, with object keys sorted
  recursively. It is independent of framing and compression.
- Optional `<table>.json` files contain ProtoJSON messages in frame order.
  They are never read as package inputs.

The directory publication implementation is tested on Linux.

Run `cargo test --locked --manifest-path draft/library/Cargo.toml` from the repository root.

[architecture RFC]: https://github.com/aivibeflow/LLMLang/blob/main/draft/RFC.md
[ADR-029]: https://github.com/aivibeflow/LLMLang/blob/main/draft/adr/029-caller-scoped-verification-obligations.md
[ADR-030]: https://github.com/aivibeflow/LLMLang/blob/main/draft/adr/030-per-table-package-dumps.md
[ADR-033]: ../adr/033-function-signature-storage.md
