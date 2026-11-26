# ADR-034 — Prefix built-in function names with `builtin__`

- **Status** — Accepted
- **Accepted** — 2026-11-27
- **Date** — 2026-11-27
- **Scope** — Names of LLMLang built-in functions

## Context

Readers and tools need a consistent spelling convention for functions provided by the language itself. Without a common prefix, recognizing those names requires knowing each built-in separately.

## Decision

Every LLMLang built-in function name starts with `builtin__`, spelled with two underscores after `builtin`. The system call built-in is named `builtin__syscall`.

## Consequences

Built-in function names share a visible marker in source text. Existing built-ins with names that lack the prefix need to adopt the new spelling. A convention based on a list of individual names would avoid renaming existing built-ins but would require readers and tools to consult that list.
