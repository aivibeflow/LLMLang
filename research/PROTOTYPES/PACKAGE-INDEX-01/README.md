# Package Index Logical Model Prototype 01

**Status:** exploratory executable model; not a normative LLMLang implementation.

## Run

Requires Python 3.11+.

```sh
PYTHONPATH=../PACKAGE-IDENTITY-01 python -m unittest discover -v
PYTHONPATH=../PACKAGE-IDENTITY-01 python -m py_compile package_index.py test_package_index.py test_streaming_merge.py test_external_validation.py test_package_archive.py package_closure.py test_package_closure.py package_provider.py test_package_provider.py test_provider_stress.py benchmark_package_provider.py content_store.py test_content_store.py ../PACKAGE-IDENTITY-01/package_identity.py
PYTHONPATH=../PACKAGE-IDENTITY-01 python benchmark_package_provider.py --sizes 1000 5000
```

## What it tests

- Four logical tables: objects, dependencies, exports, modules.
- Primary-key uniqueness, scalar validation, and cross-table references.
- Canonical table ordering and order-independent logical hashing.
- Merge deduplication for identical records and rejection of conflicting records.
- Lazy k-way merge of already sorted table streams with O(k) merge state, where k is the number of input streams.
- Detection of unsorted inputs and duplicate keys within an individual stream.
- Bounded-memory cross-table reference validation using temporary JSONL spools, bounded external-sort runs and bounded-fan-in merge passes, and sorted merge joins.
- Commutativity, associativity (for conflict-free inputs), and idempotence.
- Explicit external dependency edges that do not imply package membership.
- Exact dependency-closure resolution for closure, roots_only, and closure_with_optional, including cycles, shared dependencies, conditional selections, and snapshot consistency.
- Disk-backed Provider-to-archive construction using SQLite traversal state, sorted table iterators, and one-at-a-time verified object payload streams.
- A backend-neutral `ContentStore` / `ContentStoreSnapshot` read contract and an append-only SQLite prototype with WAL-pinned read transactions, exact-hash metadata lookup, typed dependency-index rows, and incremental BLOB streams.
- Provider integration tests proving that an already-open snapshot does not see objects committed by a concurrent writer, while a newly opened snapshot does.
- Stress coverage for 1,200-object chain and high-fan-out graphs.
- A subprocess-isolated benchmark harness for chain, diamond, high-fan-out, and many-dependency graphs, reporting wall time, throughput, traced Python peak, process peak RSS, temporary-directory high-water size, archive size, and verification.

## File index

- Implementation: [package_index.py](package_index.py), [package_archive.py](package_archive.py), [package_closure.py](package_closure.py), [package_provider.py](package_provider.py), [content_store.py](content_store.py)
- Benchmark: [benchmark_package_provider.py](benchmark_package_provider.py)
- Tests: [test_package_index.py](test_package_index.py), [test_streaming_merge.py](test_streaming_merge.py), [test_external_validation.py](test_external_validation.py), [test_package_archive.py](test_package_archive.py), [test_package_closure.py](test_package_closure.py), [test_package_provider.py](test_package_provider.py), [test_provider_stress.py](test_provider_stress.py), [test_content_store.py](test_content_store.py)

## Limitations

- Uses in-memory Python dictionaries/lists and a prototype JSON canonicalizer.
- Supports only sha256 hash spellings in this experiment.
- Streaming merge and external-memory cross-table reference validation are implemented as separate passes. Validation uses temporary disk space proportional to index/reference volume and bounds in-memory sort chunks with `max_records_in_memory` and caps each merge pass at 32 open runs.
- A deterministic streaming ZIP archive writer/verifier is implemented as an experiment. It parses the v1 TOML manifest, requires its `index.path` to identify the index-table directory, recomputes the logical index hash using the identity prototype's canonical typed encoding (external sorting keeps record sorting bounded), checks every declared root against included object membership, and recomputes/compares the Package Content Root Hash. It also streams object payloads in 1 MiB chunks, verifies SHA-256 Content Hashes and declared sizes, validates cross-table references, and atomically replaces the destination only after a complete build. The verifier repeats these checks from archive contents.
- The writer uses fixed ZIP timestamps/permissions, stored entries, and stable entry ordering; byte-for-byte determinism is covered by tests. ZIP, JSONL table entries, entry names, and manifest placement are prototype choices only. This is not a normative LLMLang archive or binary index format. The manifest's `index.path` is treated as a directory prefix in this prototype, with one JSONL file per logical table; this differs from the illustrative future `index.bin` candidate.
- Build-time temporary disk usage is proportional to the spooled logical index plus the temporary archive. The verifier streams object checks but ZIP central-directory metadata is handled by Python's `zipfile` library.
- `package_closure.py` remains an in-memory reference resolver. The integrated `package_provider.py` stores its traversal queue, visited-object metadata, and dependency rows in an on-disk SQLite database, with a configurable SQLite page cache and bounded row batches. This is not a strict constant-memory guarantee: configured sort chunks, ZIP central-directory metadata, individual edge/module rows, and caller-provided condition selections also consume memory.
- The provider reads only reachable objects and outgoing edges, streams sorted index tables into the archive builder, and opens one object payload at a time. A benchmark-driven SQLite index on `(processed, hash)` accelerates pending-queue selection; initial before/after results are recorded in `research/PACKAGE-SYSTEM.md` §17. It stages the archive and checks the snapshot token again before publishing the destination.
- Conditional expressions are not interpreted; eligible conditional edges require explicit caller-supplied boolean selections. Exports and modules are included when the snapshot adapter supplies `get_exports()` and `get_modules()`; otherwise those tables are empty.
- The SQLite Content Store is an exploratory derived-store backend, not a production Toolchain backend. It has no crash/recovery protocol beyond SQLite transactions, no garbage collection, multi-process repository lease, backup/restore contract, migration framework, or canonical SPG dependency extractor. SQLite WAL read snapshots are live transaction leases; callers must close streams and the snapshot promptly.
- Dependency edges are supplied by a semantic/indexing layer and stored immutably by exact source Content Hash. The store does not infer dependency semantics from opaque payload bytes. The current `sha256:` spelling and SQLite schema are prototype-only.
- Does not implement binary serialization, compression, block directories, sparse lookup, multi-provider composition, or provenance authentication.
- The Toolchain Server Prototype 01 is still not a usable Content Store adapter: its in-memory API has no public persistent object-store interface or canonical typed dependency extractor. `content_store.py` validates the backend-neutral read contract against a standalone SQLite prototype, but it is not wired into the Toolchain Server or its semantic object model.
- Policy execution is prototyped, but final dependency taxonomy, typed condition evaluation, and normative snapshot/provider semantics remain open.
- Prototype hash encoding is not the final LLMLang canonical encoding or digest standard.
