# ADR-034 — Prefix built-in function names with `builtin__`

- **Status** — Accepted
- **Accepted** — 2026-11-27
- **Date** — 2026-11-27
- **Scope** — Names and package visibility of LLMLang built-in functions

## Context

Readers and tools need a consistent spelling convention for functions provided by the language itself. Without a common prefix, recognizing those names requires knowing each built-in separately. Direct calls to built-ins couple the calling package to primitives provided by the toolchain.

## Decision

Every LLMLang built-in function name starts with `builtin__`, spelled with two underscores after `builtin`. The system call built-in is named `builtin__syscall`.

Only code in the package named `builtin` may reference or call a built-in function directly. The toolchain checks the owning package of each implementation, including implementations reached through dependencies and unbound bodies. This restriction applies to scalar error statements that represent `builtin__fail` and to native source references.

The `builtin` library exposes typed interfaces for the primitives it wraps. A call such as `builtin::syscall` is an ordinary call through an interface pinned to an implementation and its required contract. The `stdlib` package depends on `builtin` and forwards through those interfaces while retaining public names such as `stdlib.syscall` and `stdlib.write`.

## Consequences

Built-in function names share a visible marker in source text. Existing built-ins with names that lack the prefix need to adopt the new spelling. A convention based on a list of individual names would avoid renaming existing built-ins but would require readers and tools to consult that list.

Existing direct calls in `stdlib` move to `builtin`. Forwarding wrappers and their callers record new implementation identities and exact call pins. Native example imports load `builtin` before `stdlib`.
