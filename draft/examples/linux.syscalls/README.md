# Native Linux syscalls SPG package

This Linux x86-64 example uses repository profile `llmlang.spg.tables.v3`
and language version `0.1.0`. It includes a manifest and a Protobuf/LZ4 dump,
Content Hash index, and debug ProtoJSON file for each of the twelve tables.
Package metadata selects version `v6.12`, the pinned Linux kernel tag. Every
binding references that version.

The function table contains the 358 native declarations from the pinned
[Linux syscall source](../../../packages/linux.syscalls/provider/src/native.llmlang).
Each `canonicalBody` stores the corresponding LLMLang function text. The
355 unsafe interfaces bind directly to those implementations. The
`stackless`, `restorer`, and `kernel` entries remain unbound because they
use dedicated continuation profiles. The function table has no wrapper rows.

Contract rows carry the typed native signatures. The example supplies no
behavioral rules, layout records, or verification evidence. The Rust SPG
library loads the package and resolves its graph references. Native builds
require a backend that supports these syscall bodies and signatures.
