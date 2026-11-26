# Linux syscalls SPG package example

This is the `linux.syscalls` package in repository profile
`llmlang.spg.tables.v2` with language version `0.1.0`. The directory contains
the manifest and a table-specific Protobuf/LZ4 dump and Content Hash index for
each of the twelve tables. Package metadata selects version `0.1.0`.

The package projects the existing [Linux syscall snapshot](../../../packages/linux.syscalls/README.md)
into SPG tables. It contains 393 public interfaces, 393 native implementation
references, their exact version bindings, both public and provided contracts,
and their clauses. The function records retain native ABI information, provider
file digests, and declarations. Contract rule predicates retain the native
clause category and original text. The provider sources remain in the source
package. Structure, layout, and verification tables are empty because this
projection supplies no SPG structure identities, layouts, or verification runs.

The Rust SPG library has checked a full read with `load` and reference resolution
with `load_graph`. Two serializations produced identical files. The scalar
server and compiler currently accept scalar implementations. This package
requires a native backend for its provider references and contracts.
