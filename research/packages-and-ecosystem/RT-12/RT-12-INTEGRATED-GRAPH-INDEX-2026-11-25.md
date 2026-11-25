# RT-12 integrated, generation-bound semantic graph lookup

**Date** 2026-11-25 · **Plan** §4.1 · **Issue** [#319](https://github.com/aivibeflow/LLMLang/issues/319)

A graph query traverses typed forward calls and contract edges, reads reverse call occurrences, returns reachable contracts, and discovers providers by contract, target and ABI. SQLite stores forward and reverse projections over the same ordered edge occurrences. Its recursive query traverses a cyclic graph while treating visited nodes as a set. It begins with the queried node even when that node supplies no graph facts. Reverse projection retains multiple typed occurrences. Contract and provider tables carry their generation in every key.

The authoritative input is an independent closed inventory. The reader validates all materialized row sets for the generation, then executes the indexes or scans the exact source inventory. Both methods use the same requested graph semantics. A WAL reader pins one snapshot while a writer publishes a successor in one transaction.

| Candidate indexed view | Disagreeing unchecked query projections |
| --- | --- |
| Exact inventory and reversed insertion order | None |
| Previous providers under the new generation | Two provider results |
| Previous contracts under the new generation | Eight contract results |
| Previous edges under the new generation | Eight traversals, eight contract results and two provider results |
| One call occurrence changed to a documentation edge | Four reverse results |
| Missing provider rows | Six provider results |
| Missing full inventory | Eight traversals, eight reverse results, eight contract results and six provider results |

All 96 selected results agree with the independent direct inventory scan after admission or fallback. The unsafe WAL comparator mixes old reachable contracts with the new provider projection and returns a view corresponding to neither revision. The qualified reader recovers the previous result from its transaction, or through retained immutable generation rows after the head moves. Provider results are exact candidates in the declared scope. Selection and provider conformance require separate checks.

These scoped checks support sharing one exact admission boundary across traversal, reverse edges, contracts and provider queries. Each projection preserves the information required by downstream queries. The index validates content and cannot infer completeness from matching labels or row counts. The fixture uses full metadata scans for validation and local SQLite transactions. Production schema, compact proofs of completeness, scale, trust and latency remain open.

Reproduce with Python 3.12.14 and SQLite 3.53.1 from the repository root.

```bash
study=research/packages-and-ecosystem/RT-12/INTEGRATED-GRAPH-INDEX-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two independently constructed database sets reproduced the full comparison byte for byte.
