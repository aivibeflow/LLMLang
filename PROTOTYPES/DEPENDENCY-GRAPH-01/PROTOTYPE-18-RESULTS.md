# Prototype 18: Requirement Evolution and Semantic Impact — Results

**Status:** Research prototype; source and focused tests committed.  
**Related research:** [Research Scenario 18](../../RESEARCH-SCENARIO-18-REQUIREMENT-EVOLUTION-AND-SEMANTIC-IMPACT.md)

## Objective

Test whether a typed Requirement IR can evolve as immutable content-addressed states, while propagating semantic impact only through exact hash-relevant dependencies and keeping provenance/lineage separate.

## Implemented

`src/requirement_evolution.py` reuses the existing semantic graph and implements:
- immutable requirement state creation;
- snapshot-local selection keys that are excluded from semantic content hashes;
- derived artifacts with exact hash-relevant input dependencies;
- separate lineage records (`supersedes`, `split_into`, `merged_from`, `clarifies`, `rephrases`);
- direct and transitive reverse dependency impact;
- active-baseline dependent filtering;
- verification-key generation over exact artifact closure;
- snapshot evolution, split, merge, and three-way branch merge reporting.

## Focused tests added

Nine tests cover:
1. snapshot selection key does not affect semantic content hash;
2. one caller's semantic requirement change impacts its formal clause, caller contract, tests, and verification record;
3. unrelated caller contract and generic callee contract are not in that impact closure;
4. provenance-only lineage does not change semantic hash or verification key;
5. semantic change creates a different verification identity;
6. split creates child selections and separate lineage;
7. merge creates a new selection and separate lineage;
8. disjoint concurrent requirement edits merge;
9. concurrent edits to the same selection key conflict.

Run:

```bash
cd PROTOTYPES/DEPENDENCY-GRAPH-01
python -m unittest discover -s tests -p 'test_requirement_evolution.py' -v
```

## Interpretation

The experiment supports the architecture:
- requirement content is immutable and content-addressed;
- a snapshot-local selection key is not a global semantic identity;
- semantic impact follows hash-relevant dependency edges;
- provenance/lineage is recorded separately;
- verification evidence is tied to exact semantic artifact closure;
- split/merge and concurrent edits operate on snapshot selections.

The generic `calculate_tax` contract remains outside the preferred-caller requirement's reverse dependency closure because it accepts a generic explicit rate input and does not depend on the preferred caller's rate policy.

## Execution status

The source and focused tests were added and re-read from GitHub. The local execution environment could not run the repository test suite in this operation. The new tests were **not executed locally**; no passing-test claim is made. GitHub Actions status was not established.

## Limitations

- no automatic semantic-diff classification;
- no proof that dependency edges are complete;
- no automatic conflict resolution or rebase;
- structural snapshot merge is not a distributed transaction;
- no distinction yet between re-derive, re-test, re-prove, and human-review actions;
- no proof of source implementation conformance;
- finite Requirement IR analyzer from Prototype 17 remains limited to finite domains.

## Result

Prototype 18 provides an executable data-model direction for requirement evolution. It does not yet implement a full impact planner. The next step should classify impact actions and test dependency completeness, rather than expand the Requirement IR expression language.
