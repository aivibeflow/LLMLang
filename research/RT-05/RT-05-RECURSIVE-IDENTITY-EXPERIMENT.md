# RT-05 Recursive Identity Experiment

**Status:** Executable comparison over finite declaration graphs

## 1. Decision under study

Content-addressed calls can refer to exact immutable callee versions. Directly putting each exact callee hash in its caller's hash preimage assumes those hashes already exist. A recursive component violates that construction order. This experiment checks how alternative representations address both the group and its callable members, and which dependents must acquire new addresses when it changes. [LL-005](../../TODO.md#ll-005--define-hash-relevant-dependency-edges-and-cycles) · [Identity decision matrix](../RT-24/RT-24-IDENTITY-DECISION-MATRIX.md)

Unison provides a concrete precedent for hashing mutually recursive definitions as a cycle and addressing a member by the cycle hash plus a position. This experiment uses an exhaustive structural search for its small fixtures. It does not reproduce Unison's canonicalization algorithm. [Unison literal hash reference](https://www.unison-lang.org/docs/language-reference/literal-hash-references/) · [Unison FAQ on mutually recursive definitions](https://www.unison-lang.org/docs/usage-topics/general-faqs/)

## 2. Models compared

| Model | Address rule | Trade-off |
|---|---|---|
| DAG only | Publish declarations after all hash-relevant targets are available. Reject self recursion and larger strongly connected components | Simple publication. Recursive hash-relevant declarations require a different representation |
| Group with explicit keys | Put each strongly connected component in one immutable group. Order its members by explicit keys, include those keys in the group payload, and address each member through its position and group dependency | Keeps separate member addresses even for symmetric bodies. Changing a key changes the group hash, so key allocation becomes relevant to cross-project deduplication |
| Structural group | Use the lexically least JSON encoding across the member permutations. Encode internal calls by position and external calls by exact address | Stable under display renames without allocating keys. Symmetric members can share one value address. The reference implementation searches factorially many permutations and rejects components above six members |

The prototype uses the existing experimental Content Store. Each group commits its ordered bodies and external dependencies. A member record depends on the group. A caller outside the group depends on the exact member address. No internal call requires an already-known group hash. A declaration outside every recursive component uses the same address rule in all three modes. The fixture starts from explicit, fully resolved call references and preserves the order of body tokens. [Implementation](../PROTOTYPES/DEPENDENCY-GRAPH-01/src/recursive_identity.py)

A further option is to keep some calls symbolic and pin a separate resolution snapshot. That option has a different dependency boundary. A symbolic reference can keep a body address unchanged when a target changes, but verification and cache reuse need to account for the pinned binding and its relevant closure. The current experiment compares exact-target addressing. It does not test symbolic resolution.

## 3. Observations

| Case | Observed result |
|---|---|
| Acyclic definitions | All three modes produce the same addresses |
| Self recursion and mutual recursion | Both group modes publish the fixture. DAG only rejects both cases |
| Rename display names and rewrite the corresponding references | Both group modes preserve addresses across all 24 input declaration orders |
| Reallocate one member key | Keyed addressing changes the group, its member addresses, and the caller. Structural addressing preserves them |
| Two symmetric members | Structural addressing returns one member value address. Explicit keys keep the two member addresses distinct while sharing a group |
| Edit one member, or remove the edge that closes the cycle | Both schemes change the two former member addresses and their caller. The independent declaration keeps its address |
| Change an external dependency or reorder body tokens | The group address changes in each case in both schemes |

For the structural fixture, two orders that produce the same minimum encoding differ by a symmetry of the ordered bodies and their references. Positions attributable to distinct symmetry classes are disjoint. Using the lowest possible position for each member therefore gives tied members the same address. The tests compare the component finder against mutual reachability on all 512 directed three-node graphs and compare member equality against explicit automorphism enumeration for each strongly connected graph in the 729-case ordered-call corpus.

## 4. Implications for the RFC

- Group-level invalidation is the cost of pinning recursive implementation closures in these models. A change in one member can change an outside caller's address through the group even if the caller body is unchanged. A future build experiment should measure the number and size of affected groups and compare exact implementation dependencies against Contract-level call dependencies.
- A shared structural value address can represent two independent managed occurrences. If the editor must modify or review them separately, their continuity needs a slot, lineage, or another explicit selector outside the value address.
- Adding explicit ordering keys gives the format a stable input. The project must decide whether those keys describe semantic binding order or managed occurrence identity. The answer determines whether two separately allocated but structurally identical groups should deduplicate.
- The group/member fixture digests are distinct experimental domains. This evidence leaves open the canonical encodings for `OpHash`, `ImplHash`, recursive types, and conformance judgments. It also leaves parsing, typechecking, recursive evaluation, efficient canonical labeling, and graph import to later experiments. [Draft glossary](../../draft/GLOSSARY.md) · [Identity lifecycle experiment](RT-05-IDENTITY-LIFECYCLE-EXPERIMENT.md)

## 5. Reproduction

From `research/PROTOTYPES/DEPENDENCY-GRAPH-01`:

```sh
python -B -m unittest -v tests.test_recursive_identity tests.test_semantic_graph
```

The expanded semantic dependency workflow selection passed locally with 147 tests, including nine recursive identity cases, on Python 3.12.14 at base `72822973f7cc9fd33ede66aad05e844bf25d5bd3` with the research working tree changes. [Fixtures](../PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_recursive_identity.py) · [Workflow](../../.github/workflows/semantic-dependency-index.yml)
