# RT-05 Identity Lifecycle Experiment

**Status:** Executable comparison of continuity rules

**Scope:** Selection states, immutable values, and explicit lineage in the dependency graph prototype

## 1. Hypothesis

An exact value hash can deduplicate two implementations while leaving their managed occurrences independent. To make a change or merge refer to one occurrence, the toolchain needs a selector that survives the relevant edits, or explicit evidence linking the old and new occurrences. Test whether the three approaches in the RT-24 decision matrix provide that evidence under the same lifecycle cases. [RT-24 identity decision matrix](../../toolchain-and-collaboration/RT-24/RT-24-IDENTITY-DECISION-MATRIX.md)

## 2. Rules under comparison

| Model | Source of continuity | Cost of the rule |
|---|---|---|
| R-A, stable entity ID | Match the same unique ID across both states, even when its scope changes | Edits must preserve IDs, while independent copies and recreations need fresh IDs. Import and collision policies must preserve this distinction |
| R-B, values and explicit lineage | Each state has explicit selections. A relation links endpoints in the exact compared states | Unlinked entries stay unmatched even when values or selectors coincide. To treat a selector as persistent would introduce scoped identity |
| R-C, occurrence and scoped slot | Match the same key in the same scope. A relation can link a move across scopes | The key must remain attached to the managed occurrence. Reusing it for a new lifetime or deriving it from a position can silently misidentify the occurrence |

All three use the existing immutable value store. A display alias is metadata in this fixture. The occurrence digest combines the value, the context value, and the scoped slot. Its digest changes as those inputs change, even if the slot stays continuous. A separate fixture revision digest commits the full selected state, including aliases, so that supplied lineage can be rejected after an endpoint changes. Equal revision digests identify equal fixture states. Histories that arrive at those states still need a separate identity.

Explicit lineage supports one-to-one continuation, one-to-many split, and many-to-one merge. It reserves both sides of the relation before implicit matches run. A record with stale revisions, repeated or missing endpoints, or invalid cardinality is rejected. Under the stable-ID rule, an explicit continuation also has to preserve the ID. The experiment uses supplied lineage as input, with no claim about its author or authority. [Implementation](../../PROTOTYPES/DEPENDENCY-GRAPH-01/src/identity_lifecycle.py)

## 3. Results

| Case | Observation |
|---|---|
| Display alias change and exported name change | In the fixture, an alias change preserves value and occurrence hashes. An exported name changes the stored value when included in the operation payload |
| Independent copies of identical content | Both copies share one value hash and have different occurrence hashes. ID and scoped slot match the two copies separately when one is edited. Lineage-only matching needs both links to establish continuity |
| Cross-scope move | A preserved stable ID follows the move. A scoped key and lineage-only matching need an explicit link across the old and new scopes |
| Context state change in the same scope | The occurrence hash changes while the scoped key continues. The occurrence hash cannot itself serve as the continuity selector |
| Split and merge | All three consume the declared endpoints and preserve the given one-to-many or many-to-one relation |
| Deletion and exact recreation | A fresh stable ID or fresh slot identifies a new lifetime. A reused slot gives a false continuation. With no lifetime token or persisted history, equal endpoint states cannot distinguish recreation from survival |
| Reorder of two identical call values | Stable IDs and explicit lineage follow the two moved occurrences. A key derived from the ordinal matches the old positions instead |
| Branch merge of two selected copies | The existing selection merge accepts independent key edits and rejects divergent edits to one key. This checks the value selection merge under known continuity |

Git's rename detection can suggest a match by content similarity or equality. The identical-copy and recreation fixtures explain why such a match cannot establish lifecycle continuity by itself in this model. When order participates in behavior, an explicit position-independent selector also leaves room for the ordering rule to be represented separately, as in COR-11. [Git diffcore documentation](https://git-scm.com/docs/gitdiffcore#_diffcore_rename_for_detecting_renames_and_copies) · [Actor delivery experiment](../../language-design/RT-03/RT-03-04-SHARED-SEMANTICS-CORPUS.md#9-cor-11--actor-traces-and-failure-policies)

## 4. Implications and remaining work

For the bounded comparison, global IDs reduce the amount of explicit lineage needed for moves. They require allocating and retaining a distinct ID for each independently managed item. Scoped slots can avoid a global allocation policy when most continuity stays local. They still need lifetime and migration rules. Content with explicit lineage offers deduplication with no implicit cross-state matches. Its effectiveness depends on the editing workflow recording enough relationships before a refactor or merge.

The cases narrow what a future RFC must specify for LL-002 and LL-006. A managed selector needs a scope, a lifetime, and a rule for when it may be carried across edits. A historical lineage record needs stronger endpoint evidence than a digest of the selected data when equal states can recur. The follow-on experiment uses exact caller obligations in extraction, inlining, split, and a changed import parent. [Call site refactoring experiment](RT-05-RT-20-CALL-SITE-REFACTOR-EXPERIMENT.md)

The fixture uses experimental JSON-based hashes from the existing prototype. The cases do not establish a canonical SPG, a typed hash envelope for `OpHash` or `ImplHash`, general behavioral equivalence, Git import/export, or graph-wide semantic merge. The identity candidates remain open for those comparisons. [Open decisions](../../../PLAN.md#open-design-questions) · [Glossary](../../../draft/GLOSSARY.md)

## 5. Reproduction

From `research/PROTOTYPES/DEPENDENCY-GRAPH-01`:

```sh
python -B -m unittest -v tests.test_identity_lifecycle tests.test_semantic_graph
```

The expanded semantic dependency workflow command passed locally with 122 tests, including nine lifecycle cases, on Python 3.12.14 at base `72822973f7cc9fd33ede66aad05e844bf25d5bd3` with these working tree changes. Full discovery ran 370 tests with one skip and two unsuccessful tests. The same two unsuccessful tests reproduced in a clean archive of the base commit under the same environment. The bounded requirement analysis returned `NEEDS_REVIEW` where the suite expected `UNKNOWN`, and the missing solver test received `PermissionError` for its deliberately unavailable command. [Fixtures](../../PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_identity_lifecycle.py) · [Workflow](../../../.github/workflows/semantic-dependency-index.yml)
