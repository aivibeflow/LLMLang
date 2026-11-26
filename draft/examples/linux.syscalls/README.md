# Native Linux syscalls SPG package

This Linux x86-64 example uses repository profile `llmlang.spg.tables.v4`
and language version `0.1.0`. It includes a manifest and a Protobuf/LZ4 dump,
Content Hash index, and debug ProtoJSON file for each of the thirteen tables.
Package metadata selects version `v6.12`, the pinned Linux kernel tag. Every
binding references that version.

The function table contains the 358 native declarations from the pinned
[archived Linux syscall source](https://github.com/aivibeflow/LLMLang/blob/744aaf3f98e357a5375b55a67a538d7295d3608c/packages/linux.syscalls/provider/src/native.llmlang).
Each `canonicalBody` stores the LLMLang body block with a call to
`stdlib::syscall`. The manifest selects [stdlib](../../stdlib/README.md)
version `0.1.0`, and every call compatibility obligation pins the same
`stdlib.syscall` implementation and contract. During lowering, the server
converts typed operands to ABI words and fills unused slots with zeros.
Parameter and result types
are stored in `function_signatures` and referenced by `functionSignatureHash`. The
355 unsafe interfaces bind directly to those implementations. The
`stackless`, `restorer`, and `kernel` entries remain unbound because they
use dedicated continuation profiles. The function table has no wrapper rows.

Contract rows carry typed native signatures, and the call obligations are
unchecked. The native MCP server resolves the links and builds the package
after importing its `stdlib` dependency.
