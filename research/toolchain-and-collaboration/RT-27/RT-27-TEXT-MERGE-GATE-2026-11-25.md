# RT-27 clean Git merge trees and semantic graph admission

**Date** 2026-11-25 · **Plan** §4.2, R-STORE-005 · **Issue** [#320](https://github.com/aivibeflow/LLMLang/issues/320)

The fixture stores a program root, a consumer contract and a selected provider in separate canonical records. One Git contributor edits the contract and another edits the provider. Both parents individually satisfy their selected contract. Six input cases cover a numeric bound, permitted effects, ABI declarations and combinations of those requirements.

The runner compares native `git merge-tree --write-tree` with a typed composition of the disjoint facts. It compiles and runs a small C provider model on all three admitted inputs to collect results and effect markers. The ABI constraint is an independent declared metadata check. The candidate validation examines the combined contract and provider before selecting the corresponding semantic root.

| Condition | Git reports a clean tree | Semantic validation |
| --- | ---: | --- |
| Numeric limit and new provider remain compatible | 4 | All admitted |
| Provider exceeds the tightened limit | 4 | All refused |
| Provider performs a newly excluded effect | 4 | All refused |
| Provider declares a removed ABI | 4 | All refused |
| All three constraints are violated | 4 | All refused |
| Provider changes to another permitted effect | 4 | All admitted |

The repetitions cover Git SHA-1 and SHA-256 object formats with and without a binary merge attribute. Git cleanly combines edits to separate paths under both attribute policies. Every tree decodes canonically and agrees with the candidate assembled from the two edited records. Sixteen candidates violate a joint semantic constraint. Eight satisfy all declared constraints and get an exact validated graph identity.

Treat the Git tree as an input to complete-state semantic merging and validation. Cross-file contracts can fail even if all paths merge cleanly and every individual record decodes. A validated candidate root and its current receipts are the publication prerequisite. The fixture records the accepted or refused candidate without changing an authoritative repository. It checks bounded C observations and explicit ABI labels. General proof authority, real foreign ABI equivalence and production merge orchestration remain open.

Reproduce with GCC, Git 2.52.0 and Python 3.12.14 from the repository root.

```bash
study=research/toolchain-and-collaboration/RT-27/TEXT-MERGE-GATE-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two independent sets of temporary repositories and native builds produced byte-identical evidence.
