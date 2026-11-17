# Package Index Logical Model Prototype 01

**Status:** exploratory executable model; not a normative LLMLang implementation.

## Run

Requires Python 3.11+.

```sh
PYTHONPATH=../PACKAGE-IDENTITY-01 python -m unittest discover -v
PYTHONPATH=../PACKAGE-IDENTITY-01 python -m py_compile package_index.py test_package_index.py test_streaming_merge.py test_external_validation.py test_package_archive.py ../PACKAGE-IDENTITY-01/package_identity.py
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

## Limitations

- Uses in-memory Python dictionaries/lists and a prototype JSON canonicalizer.
- Supports only sha256 hash spellings in this experiment.
- Streaming merge and external-memory cross-table reference validation are implemented as separate passes. Validation uses temporary disk space proportional to index/reference volume and bounds in-memory sort chunks with `max_records_in_memory` and caps each merge pass at 32 open runs.
- A deterministic streaming ZIP archive writer/verifier is implemented as an experiment. It parses the v1 TOML manifest, requires its `index.path` to identify the index-table directory, recomputes the logical index hash using the identity prototype's canonical typed encoding (external sorting keeps record sorting bounded), checks every declared root against included object membership, and recomputes/compares the Package Content Root Hash. It also streams object payloads in 1 MiB chunks, verifies SHA-256 Content Hashes and declared sizes, validates cross-table references, and atomically replaces the destination only after a complete build. The verifier repeats these checks from archive contents.
- The writer uses fixed ZIP timestamps/permissions, stored entries, and stable entry ordering; byte-for-byte determinism is covered by tests. ZIP, JSONL table entries, entry names, and manifest placement are prototype choices only. This is not a normative LLMLang archive or binary index format. The manifest's `index.path` is treated as a directory prefix in this prototype, with one JSONL file per logical table; this differs from the illustrative future `index.bin` candidate.
- Build-time temporary disk usage is proportional to the spooled logical index plus the temporary archive. The verifier streams object checks but ZIP central-directory metadata is handled by Python's `zipfile` library.
- Does not implement binary serialization, compression, block directories, sparse lookup, archive I/O, or provider-side dependency closure.
- Dependency policy semantics and conditional dependency evaluation remain incomplete.
- Prototype hash encoding is not the final LLMLang canonical encoding or digest standard.
