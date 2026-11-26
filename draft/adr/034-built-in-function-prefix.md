# ADR-034 — Prefix built-in function names with `builtin__`

- **Status** — Accepted
- **Accepted** — 2026-11-27
- **Date** — 2026-11-27
- **Scope** — Names and package visibility of LLMLang built-in functions

## Context

Readers and tools need a consistent spelling convention for functions provided by the language itself. Without a common prefix, recognizing those names requires knowing each built-in separately. Direct calls to built-ins couple the calling package to primitives provided by the toolchain.

## Decision

Every LLMLang built-in function name starts with `builtin__`, spelled with two underscores after `builtin`. The system call built-in is named `builtin__syscall`.

Only code in the `stdlib` package may reference or call a built-in function. The toolchain rejects direct uses of built-ins in every other package. Other packages can access operations backed by built-ins through public interfaces exposed by `stdlib`.

## Consequences

Built-in function names share a visible marker in source text. Existing built-ins with names that lack the prefix need to adopt the new spelling. A convention based on a list of individual names would avoid renaming existing built-ins but would require readers and tools to consult that list.

Existing direct uses of built-ins outside `stdlib` must move to calls through its public interfaces or be rewritten.
