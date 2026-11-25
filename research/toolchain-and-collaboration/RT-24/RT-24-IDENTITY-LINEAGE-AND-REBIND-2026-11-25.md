# RT-24 stable identity through rename, split and merge

A logical entity's stable ID, the exact operation hash and a source-to-target lineage decision answer different questions. A presentation rename can preserve operation identity. An externally observable rename can retain the entity and still change the exact operation hash. Split and merge require explicit lineage and a caller-specific binding.

## Candidate transitions

| Transition | Stable selection | Call-site effect |
| --- | --- | --- |
| Display rename | Same entity and exact operation in a new snapshot | Existing exact call binding remains valid. |
| Public name change | Same logical entity with changed operation hash | Each caller needs a matching rebind receipt. |
| Split | One old entity maps to two new entities through explicit lineage | Legacy and modern callers use separately authorized destinations. |
| Merge | Two old entities map to one new entity through explicit lineage | Each prior caller has its own checked transition to the merged operation. |
| Equal semantic content in two independently managed entities | Shares an operation value, while stable IDs remain distinct | A same-content substitute requires its own selected occurrence and lineage. |

The fixture binds old and new snapshots, lineage relations, a complete caller inventory, routing policy and changed-call evidence. The receipt subject includes the caller, original operation, destination operation and destination stable ID. It supplies synthetic evidence identifiers to test binding. Policy authority and proof of compatibility are separate obligations. [Identity alternatives](RT-24-IDENTITY-DECISION-MATRIX.md) · [Native Git split caller paths](RT-24-SPLIT-CALLER-PATHS-2026-11-24.md)

```mermaid
flowchart LR
    S["Old and new exact selections"] --> L["Check typed lineage"]
    L --> C["Check complete caller inventory and routes"]
    C --> E["Bind each changed caller to exact rebind evidence"]
    E --> A["Accept scoped identity transition"]
```

## Results

Across 704 cases, the five accepted profiles are the display rename with or without extra unused receipts, and the three remaining transitions with valid receipts. The other cases fail the snapshot, lineage, caller inventory, route or evidence checks. A split receipt for only the legacy caller leaves the modern route unsupported. Replacing the renamed entity with an independently managed entity of equal operation content fails exact lineage.

This comparison covers three static callers and four declared edits. General identity allocation, authority for a real split or merge, dynamic dispatch, inheritance and local policy for preserving an ID through a split remain open. [Lineage and reconciliation proposal](RT-24-IDENTITY-AND-SPG-RECONCILIATION.md)

## Reproduce

Use CPython 3.12.14. Hash seeds 37 and 71 yield evidence SHA-256 `5c0126baa4d2a8668ef5b49f93984c5403d7f64711fb3367654618f1020f5f1d`. [Evidence ledger](IDENTITY-LINEAGE-01/evidence.json)

```sh
LC_ALL=C PYTHONHASHSEED=37 PYTHONDONTWRITEBYTECODE=1 \
  python research/toolchain-and-collaboration/RT-24/IDENTITY-LINEAGE-01/check.py > /tmp/rt24-identity-lineage.json
```
