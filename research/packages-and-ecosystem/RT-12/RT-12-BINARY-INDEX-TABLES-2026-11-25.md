# RT-12 — Canonical binary package tables and streamed merge

- **Date** — 2026-11-25
- **Tracking** — [PLAN §7.2](../../../PLAN.md#72-libraries-packages-templates-and-artifact-ecosystem) · [#333](https://github.com/aivibeflow/LLMLang/issues/333)
- **Status** — Reproduced candidate encoding over the four logical tables

## Question and candidate format

Can the existing logical package index use compact table files with exact point lookups and deterministic streamed merge? This candidate keeps four separate tables. Each has a magic value, version, table tag and count, followed by an array of big-endian 32-bit offsets and the row payloads. Row layouts use raw 32-byte SHA-256 addresses, length-prefixed UTF-8 identifiers, fixed-width numeric values and explicit tags. Optional dependency conditions have a presence tag and a length-prefixed canonical JSON payload. A table reader checks exact offset coverage, row encoding and strict key order before serving lookup. [Logical index schema](PACKAGE-INDEX-LOGICAL-SCHEMA.md) · [Current logical prototype](../PROTOTYPES/PACKAGE-INDEX-01/package_index.py)

| Table | Ordered key |
|---|---|
| Objects | Raw exact hash |
| Dependencies | Source hash, then edge identifier |
| Exports | Module identifier, then name |
| Modules | Module identifier |

Lookup compares decoded logical keys. Sorting whole row bytes by their length prefixes could put short identifiers ahead of lexically earlier, longer names. The fixture includes unequal key lengths and distinct UTF-8 spellings. Streamed merge uses the existing sorted row merger and deduplicates equal records. The writer spools offsets and payload separately and adopts the completed table only after all rows succeed. It validates merged cross-table references separately through the logical index.

```mermaid
flowchart LR
    L["Sorted logical rows from each provider"] --> B["Binary tables with offset directory"]
    B --> S["Audited binary search"]
    B --> M["Merge row iterators"]
    M --> O["Deterministic binary tables"]
    O --> V["Validate logical references and identity"]
```

## Results

Three overlapping provider indexes produce one logical result and one exact set of binary table hashes in all six input orders. The full positive inventory contains 200 rows. Across the permutations, all 1,224 known-key and missing-key lookups match. After the opening audit, the longest checked lookup decodes seven of 64 rows or four of eight rows. The empty-table control preserves the four empty tables and returns a miss with zero row decodes.

| Table | Rows | Candidate bytes | Compact JSONL bytes |
|---|---:|---:|---:|
| Objects | 64 | 3,470 | 7,104 |
| Dependencies | 64 | 5,262 | 15,048 |
| Exports | 64 | 2,926 | 7,712 |
| Modules | 8 | 2,162 | 4,988 |
| Total | 200 | 13,820 | 34,852 |

The binary candidate uses 60.3% fewer bytes on the fixture, including its offset arrays. Ten malformed table controls are refused, including bad tags and offsets, duplicate or reversed keys, invalid UTF-8, unsorted members and trailing bytes. A conflicting streamed merge preserves the existing destination bytes. [Evidence ledger](BINARY-INDEX-TABLES-01/evidence.json)

## Limits

The encoding is an experimental representation for the current four table schemas and SHA-256 profile. The opening audit is linear in rows, and the lookup figures exclude that audit. File mutability, bounded production decoding, schema and digest agility, compressed blocks, optional directory integrity and multi-table publication need their own policies. Physical table bytes remain separate from the logical index hash.

## Reproduction

Run from the repository root with CPython 3.12.14. The runner generates the provider tables in a temporary directory, checks the logical oracle and reports exact physical hashes and sizes. [Codec](BINARY-INDEX-TABLES-01/tables.py) · [Runner](BINARY-INDEX-TABLES-01/run.py)

```sh
set -eu
dir=research/packages-and-ecosystem/RT-12/BINARY-INDEX-TABLES-01
observed=$(mktemp)
trap 'rm -f "$observed"' EXIT
python3 -B "$dir/run.py" > "$observed"
cmp "$dir/evidence.json" "$observed"
```
