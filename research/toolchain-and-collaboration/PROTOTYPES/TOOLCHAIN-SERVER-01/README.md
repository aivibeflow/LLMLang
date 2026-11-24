# Toolchain Server Prototype 01

**Status:** Executable in-memory lifecycle prototype; not production code  
**Research:** [RT-19 — Toolchain Server and Semantic Development API](../../RT-19/RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md)  
**Related proposal:** [ADR-015](../../../../docs/adr/015-toolchain-server-semantic-api.md)

## Purpose

This prototype tests a narrow part of the RT-19 proposal: immutable semantic objects, content-addressed snapshots, isolated workspaces, typed Change operations, optimistic revision/hash checks, acceptance, and deterministic textual export/import.

It deliberately uses a tiny generic Entity envelope because the canonical LLMLang SPG schema and mutation vocabulary are not yet settled.

## Run

Requires Python 3.11+ and the standard library only.

```bash
python -m unittest discover -s research/toolchain-and-collaboration/PROTOTYPES/TOOLCHAIN-SERVER-01 -v
```

## File index

- Implementation: [toolchain.py](toolchain.py)
- Tests: [test_toolchain.py](test_toolchain.py)

## Implemented

- Content-addressed immutable entity payloads (prototype SHA-256 envelope).
- Deterministic snapshot roots over Stable ID → Content Hash mappings.
- Explicit Workspace and Change Set identifiers.
- Typed add/update/remove operations with expected object hashes.
- Atomic Change Set validation before publishing a new workspace root.
- Workspace revision compare-and-swap and isolated parallel workspaces.
- Acceptance as a separate operation from export.
- Canonical JSON repository fixture with entity and snapshot hash verification.
- Atomic single-file replacement and detection of external edits using the expected file hash.

## Not implemented

- The LLMLang SPG schema, real language parser/type checker, or compiler.
- Persistent database backend, crash recovery, garbage collection, or cross-process locking.
- MCP, CLI, IDE, REST, or CI adapters.
- Multi-file export generations, Git index/commit/push integration, or semantic merge.
- Authentication, authorization, policy engine, audit log, or sandboxing.
- Final canonical serialization, hash algorithm policy, or stable public API contract.

The JSON fixture is a test interchange format, not a proposed LLMLang source syntax or normative repository format. The Python SHA-256 encoding is also prototype-only.

## What the prototype can establish

Passing tests can provide evidence for the local state-transition and precondition logic in this small model. It cannot establish correctness of a future SPG implementation, database durability, filesystem portability beyond the tested environment, MCP interoperability, or the overall RT-19 architecture.


## CI evidence and reproducibility

The required `toolchain-workspace / focused-tests` job runs this directory on Python 3.12.16 (Ubuntu 26.04.1, runner image `ubuntu-26.04` / `20261111.196.1`). It executes `python -m compileall -q .` and `python -m unittest discover -s . -p 'test_toolchain.py' -v`. CI run [44746782815](https://github.com/aivibeflow/LLMLang/actions/runs/44746782815), on merge commit `06d8ac1a9a0982d5cb7319d36b4dcabec77faf79` (tree `997cfdf5dfc8518862ce95a5683d0e68dd6ca7e8`, identical to main snapshot `f560d0f9893f882a6756f1f0a3b070ea7ba1a09f)), passed all **9 tests** in 0.007 s. This confirms the in-memory workspace lifecycle model and its file import/export checks at the recorded source tree; it does not validate a persistent backend, crash recovery, multi-file transactions, Git integration, MCP, authorization, or a production SPG schema.
