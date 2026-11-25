# RT-12 — Integrity and reconstruction of an optional sparse directory

- **Date** — 2026-11-25
- **Tracking** — [PLAN §7.2](../../../PLAN.md#72-libraries-packages-templates-and-artifact-ecosystem) · [#333](https://github.com/aivibeflow/LLMLang/issues/333)
- **Status** — Reproduced exact lookup and reconstruction controls

## Question and candidate rules

Can a derived sparse directory establish that a key is absent from a package index if the directory only carries its own checksum? The fixture reuses the 8,192-record canonical stream from the compression comparison. A directory row holds a block's first key, byte offset, compressed length and digest. Three projections use gzip with two block sizes and bzip2 with one. The canonical stream digest names the logical table in this model. The directory digest names each physical projection independently. [Index compression comparison](RT-12-INDEX-COMPRESSION-2026-11-25.md) · [Package system](PACKAGE-SYSTEM.md)

The self-check policy accepts a directory that names the intended logical root and carries matching local checksums. The pinned policy obtains the directory digest, codec and block size from trusted fixture state. The exact directory commits to each candidate block's bytes and range start. On missing or damaged projection data, the pinned policy checks the complete canonical stream against the logical digest and rebuilds the projection. It returns unavailable if it cannot authenticate a usable projection or canonical stream.

```mermaid
flowchart LR
    P["Known logical root and layout pin"] --> D["Validate optional directory and selected block"]
    D -->|valid| O["Exact hit or miss"]
    D -->|unusable| C["Verify canonical sorted stream"]
    C -->|matches| R["Rebuild exact projection"]
    R --> O
    C -->|unavailable| U["Lookup unavailable"]
```

## Results

The matrix covers 33 lookups across 11 conditions, including exact hits in the leading and middle blocks and one expected miss. Self-checking reports three incorrect results for a leading hit. Omitting a leading directory row or routing to a shortened block yields a false miss; routing to a block with changed record metadata returns the wrong row bytes. In each case the local checksums remain internally consistent.

The pinned policy returns the oracle's exact result in all 27 checks with sufficient evidence. The remaining six checks return unavailable because the optional directory is absent and the canonical stream is missing or mismatched. Corrupting one compressed block causes a rebuild for a query routed to that block. Queries routed elsewhere continue from the valid directory and their own checked compressed block. This behavior establishes a scoped lookup result and supplies no whole-artifact availability claim.

All three layout choices share one canonical table digest and have distinct directory digests. Six additional lookups run under the two alternate projections' own pins and match the oracle. A directory for the same table at a different block size is refused under the original pin and regenerated to the original bytes. [Evidence ledger](INDEX-INTEGRITY-01/evidence.json)

## Limits

The directory pin must come from an independently trusted and snapshot-bound projection record. This fixture generates pins locally from the checked canonical stream. It models fixed rows, immutable inputs and deterministic compression settings. It does not settle the package wire format, pin publication, concurrent recovery or the authority that endorses a representation. It also leaves complete archive auditing, bounded decoding of external data and canonical-row validation to their own gates.

## Reproduction

Run from the repository root with CPython 3.12.14 and the gzip and bzip2 implementations used in the compression experiment. [Runner](INDEX-INTEGRITY-01/sparse.py)

```sh
set -eu
dir=research/packages-and-ecosystem/RT-12/INDEX-INTEGRITY-01
observed=$(mktemp)
trap 'rm -f "$observed"' EXIT
python3 -B "$dir/sparse.py" > "$observed"
cmp "$dir/evidence.json" "$observed"
```
