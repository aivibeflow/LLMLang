# Package Index Logical Model Prototype 01

**Status:** exploratory executable model; not a normative LLMLang implementation.

## Run

Requires Python 3.11+.

```sh
python -m unittest discover -v
python -m py_compile package_index.py test_package_index.py test_streaming_merge.py test_external_validation.py
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
- There is no streaming archive writer yet; temporary disk capacity and cleanup behavior are operational requirements for the current validator.
- Does not implement binary serialization, compression, block directories, sparse lookup, archive I/O, or provider-side dependency closure.
- Dependency policy semantics and conditional dependency evaluation remain incomplete.
- Prototype hash encoding is not the final LLMLang canonical encoding or digest standard.
