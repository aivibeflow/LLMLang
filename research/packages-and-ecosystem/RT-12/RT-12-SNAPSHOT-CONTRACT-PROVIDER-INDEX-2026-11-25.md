# RT-12 — Snapshot-bound discovery by contract and target

Scope is PLAN §4.1 and [#319](https://github.com/aivibeflow/LLMLang/issues/319), starting from `c3b56825b682650082fb71eee7e99c2223254547` on `research/all`.

A consumer that has pinned an immutable program snapshot needs the provider candidates discoverable in that snapshot. An index that reads the current catalog after selecting an older root can return a valid provider from the wrong generation. This experiment compares current-only projection reads and generation-qualified reads in SQLite.

## Fixture and admission

Each canonical inventory contains tuples of scope, contract reference, target, and provider reference. Short labels act as exact references in the fixture. The generation root hashes the sorted closed inventory. SQLite stores a snapshot-qualified index and a replaceable latest projection. A WAL transaction publishes both projections, the counts and digests, and the selected root together. Candidate lookup filters on exact generation, scope, contract, and target and orders provider references deterministically.

```mermaid
flowchart LR
    S["Exact source inventory"] --> H["Compute generation identity"]
    H --> P["Publish index rows and root in one transaction"]
    P --> R["Reader pins generation or a WAL read snapshot"]
    R --> V["Validate projection against the closed inventory"]
    V --> Q["Query scope, contract and target"]
    Q --> C["Return candidates for later conformance and binding"]
```

A WAL read transaction pins a consistent database view. A generation-qualified query remains meaningful after the head advances only while the requested rows are immutable and retained. The fixture checks the full projection against an independently enumerated manifest. It uses no production authentication or expiry protocol.

## Observations

The runner checks 54 lookups across three catalogs, two scopes, three contract labels and three target labels. All results match a direct inventory scan, including empty queries and multiple candidates. SQLite 3.53.1 reports a primary-key search on the four filtering fields. This is query-shape evidence, with no latency measurements.

| Control for `app / v1 / linux` | Returned providers | Interpretation |
| --- | --- | --- |
| Read selected root and latest rows in one pinned read transaction | `legacy, portable` | Consistent old view |
| Read old head, then unscoped latest rows after publication | `new-native, portable` | Result belongs to the new generation |
| Read the old generation explicitly after publication | `legacy, portable` | Correct while the generation is retained |
| Substitute one provider in the retained index | Count matches, exact admission fails | Cardinality alone cannot establish integrity |

The last control leaves the row count unchanged. The exact check rejects the projection because its digest and contents differ from the expected canonical inventory. A corrupt stored digest also fails. This complements the existing snapshot-bound reverse-index study. An implementation discovery result gives a set of candidates. Contract refinement, evidence freshness and selecting an implementation are downstream decisions.

## Reproduction and limits

Use CPython 3.12.14 with SQLite 3.53.1 and an accessible temporary filesystem. The [runner](CONTRACT-PROVIDER-INDEX-01/run.py) creates and removes its own databases. The [ledger](CONTRACT-PROVIDER-INDEX-01/evidence.json) records the catalogs, queries, roots, observed plan string and control outcomes. The finite table gives the relevant categories without a chart. Mermaid syntax was inspected directly.

```sh
fixture=research/packages-and-ecosystem/RT-12/CONTRACT-PROVIDER-INDEX-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > /tmp/llmlang-contract-index.json
cmp "$fixture/evidence.json" /tmp/llmlang-contract-index.json
```

The fixture leaves cross-provider scaling, canonical digest types, durable pin lifetime, index rebuild, authorization, and atomic publication across an external store open.
