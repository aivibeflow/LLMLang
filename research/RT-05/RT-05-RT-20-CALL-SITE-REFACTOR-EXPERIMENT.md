# RT-05 / RT-20 Call Site Refactoring Experiment

**Status:** Executable experiment over the existing declaration graph

## 1. Question

When a refactor moves, duplicates, or removes a call, what lets the toolchain find the relevant occurrence and establish that the caller's obligations still hold? The experiment places real RT-20 call edges behind the three RT-05 matching policies. It also checks a finite inline substitution independently of the continuity match. [Identity lifecycle experiment](RT-05-IDENTITY-LIFECYCLE-EXPERIMENT.md) · [Contract identity and compatibility](../RT-20/RT-20-CONTRACT-IDENTITY-AND-COMPATIBILITY.md)

## 2. Evidence and scope

The structural audit derives exact edges from the baseline and candidate Snapshot declarations. It pins both Snapshot roots and identifies each endpoint by selection key, caller hash, and edge ID. The selection key distinguishes two occurrences of the same immutable caller. Each removed edge needs a transfer or an inline check. Each added edge needs a unique recorded source or an explicit classification as new. The result lists newly declared calls separately as requiring review.

An exact transfer preserves the concrete callee, target kind, guard, and required Contract hash. These checks account for call bindings. The compiler or verifier would still have to establish that arguments, execution conditions, and reachability are preserved through the refactor. In particular, the new bridge from the caller to an extracted helper needs its own validation.

The inline check supports a whole-body unary Int call in the baseline and a whole-body inline expression in the same candidate selection. It derives the outputs of the old callee and the replacement from their stored bodies. Both must satisfy the old required Contract on its explicit finite input domain, and both must return the same output for every input in that domain. This fixture treats a return value as the only observation. A language-level transformation proof would need the actual translation and its observation model. CompCert's inlining pass provides a prior example of a separate machine-checked preservation argument. [CompCert compiler documentation](https://compcert.org/doc/) · [Experiment implementation](../PROTOTYPES/DEPENDENCY-GRAPH-01/src/call_site_refactor.py)

## 3. Observations

| Case | Result |
|---|---|
| Extract a direct call into a selected helper | A stable ID follows it across owners. Scoped slots and explicit-lineage matching need a relation. The same structural check accepts the exact moved binding under all three policies and flags the new bridge for review |
| Retain the occurrence ID but change the callee, guard, or required Contract | The exact-binding check rejects the transfer. A different binding would require a different justification |
| Split one call into two selected occurrences | Both destinations need exact bindings. Listing one destination twice fails. Two baseline selections of the same caller also require separate coverage |
| Import equal selections under a different parent Snapshot | The old plan fails because the roots differ. Substituting the old root on the imported Snapshot fails integrity checking |
| Inline `x+2` in place of a call to a body that returns `x+2` | The finite check matches the actual selected replacement and accepts on inputs `0` and `3` |
| Inline `x+3` under the same required Contract | Both bodies conform because the Contract permits `x+2` or `x+3`. Equivalence fails at input `0`. An inline `x+4` fails the Contract itself |

This suggests three independent RFC questions. The editor needs a way to identify the managed occurrence. The plan needs to account for changes to exact bindings across snapshots. The verifier needs a behavioral judgment that fits the transformation, which can be stronger than Contract refinement. A Snapshot root commits to parent references in the current prototype, but the branch import fixture supplies those references in memory. Validation of imported history, authority to assert lineage, domain completeness for real source, and ordered or effectful inlining remain open.

## 4. Reproduction

From `research/PROTOTYPES/DEPENDENCY-GRAPH-01`:

```sh
python -B -m unittest -v tests.test_call_site_refactor tests.test_identity_lifecycle tests.test_contract_model
```

All seven refactor tests and the expanded 138-test workflow selection passed locally on Python 3.12.14 with these working tree changes over base `72822973f7cc9fd33ede66aad05e844bf25d5bd3`. [Fixtures](../PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_call_site_refactor.py) · [Workflow](../../.github/workflows/semantic-dependency-index.yml)
