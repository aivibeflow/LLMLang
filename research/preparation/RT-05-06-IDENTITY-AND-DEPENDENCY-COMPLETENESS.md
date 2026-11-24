# Research Preparation — RT-05/06 Identity and Dependency Completeness

**Status:** Prepared; not executed.  
**Priority:** P0 — parallel foundational work after source/semantic assumptions are made explicit.  
**Related open questions:** LL-001–LL-008; RT-05 and RT-06 gates.

## 1. Mandatory terminology prerequisite

Before changing any identity-bearing field or comparing hash envelopes, read the [Draft Glossary](../../draft/GLOSSARY.md) together with:
- [RT-20 Contract Identity and Compatibility](../toolchain-and-collaboration/RT-20/RT-20-CONTRACT-IDENTITY-AND-COMPATIBILITY.md)
- [RT-05 lifecycle experiment](../semantic-representation/RT-05/RT-05-IDENTITY-LIFECYCLE-EXPERIMENT.md)
- [RT-05 recursive identity experiment](../semantic-representation/RT-05/RT-05-RECURSIVE-IDENTITY-EXPERIMENT.md)
- [RT-24 identity and SPG reconciliation](../toolchain-and-collaboration/RT-24/RT-24-IDENTITY-AND-SPG-RECONCILIATION.md)
- [RT-24 identity decision matrix](../toolchain-and-collaboration/RT-24/RT-24-IDENTITY-DECISION-MATRIX.md)
- [Scenario 91 — versioned addresses and digest migration](../semantic-representation/RT-05/RESEARCH-SCENARIO-91-VERSIONED-CONTENT-ADDRESSES-AND-DIGEST-MIGRATION.md)
- [Scenario 92 — operation identity and implementation binding](../semantic-representation/RT-05/RESEARCH-SCENARIO-92-OPERATION-IDENTITY-AND-IMPLEMENTATION-BINDING.md)

The glossary is a terminology proposal, not an accepted encoding or normative schema.

## 2. Identity distinctions to preserve

The study must not collapse these different claims:

| Object / claim | Proposed identity | What it identifies |
|---|---|---|
| Exact immutable Contract value | Generic `ContractHash` | Contract content; not operation identity or conformance |
| Exact semantic operation version | `OpHash` | Operation definition and caller-observable contract |
| Concrete implementation artifact | `ImplHash` | Exact implementation and hash-relevant semantic dependencies |
| Conformance rule under constraints | `CCHash` | Membership predicate, not a list of discovered implementations |
| Time-bounded discovery result | Optional `CandidateSetHash` | Finite candidate set and search scope |
| Evidence for a claim | Evidence identity | Exact subject, assumptions, producer/tool and validation inputs |

Use the glossary's `ImplHash` spelling in new material. The older `PLAN.md` uses `ImpHash` in several places; record that as a documentation/schema reconciliation issue rather than silently treating the spellings as accepted aliases.

Keep these relations explicit:
- contract equality is not behavioral equivalence;
- conformance is not implementation identity;
- candidate discovery is not acceptance;
- content integrity is not publisher/verifier trust;
- semantic identity is not the same as a cache action key or output artifact address.

**Call/contract storage constraint:** Keep the callee-provided Contract owned by the callee declaration. A caller refers to the callee, and the provided Contract is resolved through that callee (`caller → callee → contract`); do not introduce a second stored copy or redundant extra reference to the callee's provided Contract. Keep any distinct caller-required contract requirement separate from the callee-provided value.

## 3. Questions

### Canonical identity
- What canonical typed payload belongs to each identity domain?
- Which schema version, semantic domain, digest suite, media type/size or encoding version is committed?
- Which fields are semantic, ABI/target-dependent, build/action-specific, descriptive, provenance-only or evidentiary?
- How are algorithm agility, dual-address migration, collision handling and legacy address verification handled?
- Which observations are guaranteed by `OpHash`, and does the operation promise contract-permitted behavior or one exact implementation behavior?

### Stable identity and lifecycle
- What survives rename, move, copy, duplicate, branch import, split, merge, deletion and recreation?
- How are independently created but structurally equivalent entities distinguished from the same continuing entity?
- When is explicit lineage required, and who can authenticate it?
- How do content-only identity and stable ID plus content hash behave under edits and concurrent branch changes?

### Cycles and dependency closure
- How are mutually recursive groups represented and addressed?
- Which edge types participate in each identity preimage?
- How do call-site references, contract changes and target/runtime constraints propagate identity changes?
- How are SCCs, external dependencies and incomplete reverse-reference indexes handled?
- Which missing or negative lookups invalidate a dependency result?

## 4. Proposed common scenario matrix

Run the same source graph through the candidate identity models already recorded in RT-24; do not invent a new candidate naming scheme without updating the matrix.

| Dimension | Required cases |
|---|---|
| Names and locations | rename; file move; module move; alias/re-export |
| Duplicates | byte-identical duplicate; semantically identical independent entity; copied entity with explicit lineage |
| Lifecycle | update; split; merge; deprecate; delete/recreate |
| Recursive graphs | direct recursion; mutual recursion; SCC membership change; member insertion/removal |
| Calls | call-site retarget; preserve old callee; caller migration; shared-caller fork |
| Dependencies | positive lookup; negative lookup; fallback lookup; dynamic/provider discovery |
| Repository | import/export round trip; branch conflict; three-way merge; missing dependency |
| Versions | schema version change; digest algorithm migration; target/ABI variation |

For each case record identity before/after, expected continuity, changed dependency closure, affected callers and cache/evidence invalidation.

## 5. Method and outputs

1. Freeze the semantic observations and source fixtures inherited from the RT-03/04 work.
2. Define a typed identity envelope independently for each object category.
3. Implement a small deterministic canonical-byte fixture only after the payload fields are explicit.
4. Compare candidate identity/lineage models against the common lifecycle matrix.
5. Build a source-bound dependency extractor with explicit completeness evidence and conservative UNKNOWN.
6. Check hash propagation and reverse-reference closure against an independent graph traversal.
7. Exercise import/export and branch merge using pinned snapshots; preserve all conflicts rather than choosing a convenient identity.

Deliver:
- identity-domain table and canonical envelope candidates;
- lifecycle/lineage fixture corpus;
- edge taxonomy and SCC/closure model;
- source-bound dependency/completeness evidence schema;
- migration, collision and trust analysis;
- updated glossary cross-links, RT-24 matrix, TODO and option matrix.

## 6. Exit criteria

- Every hash field names one object/domain and its exact semantic payload.
- Caller-required and callee-provided contracts remain distinct, with provided contract storage owned by the callee.
- Stable identity continuity is backed by explicit lifecycle evidence, not name similarity.
- Recursive dependencies have a deterministic, tested treatment.
- Missing, negative, dynamic and fallback dependencies cannot silently disappear.
- Import/export and branch-conflict cases preserve identity and lineage evidence.
- Results state assumptions and do not silently settle any open LL question.

The research may recommend candidate vectors. Any accepted identity schema requires a separate project decision.
