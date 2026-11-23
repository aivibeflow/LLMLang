# RT-00 — DEP-009 SPG Admission Recheck (2026-11-23)

**Plan item:** §0.3, validate dependency edges as evidence accumulates  
**Edge:** DEP-009, RT-05 → RT-06 (`Requires`)  
**Baseline:** current `main` `0a798bfd14806c6aeddf22393b7efa2981e40d54`  
**Disposition:** Retain the scoped experimental evidence. A valid content digest does not guarantee a complete typed dependency graph. For this fixture, independent admission checking rejects an executable call whose declared `uses` edge is missing. It does not establish source inventory completeness or arbitrary schema correctness.

## Compared dependency-validation choices

| Choice | Guarantee/cost boundary | Evidence |
|---|---|---|
| Verify content addresses, then trust the producer | Low added cost; assumes producer already checked type and dependency consistency | Insufficient for untrusted or independently constructed graphs. Rehashed malformed graphs pass persistence. |
| Walk only declared dependency edges | Efficient closure over stored edges; depends on those edges being complete | Insufficient: a call can execute even when its edge is omitted, so the walk misses a real dependency. |
| Independently inspect typed instruction trees and require exact agreement with declared call edges | Adds a version-matched admission checker; catches malformed types, unresolved targets, and missing/unused edges in its supported schema | Implemented and rechecked in the closed acyclic fixture. Does not verify source-to-graph completeness. |
| Rebuild from a pinned source inventory and compare | Can detect declarations omitted before graph construction; requires exact source, profile, resolver, and inventory closure | A separate requirement, not implemented by this admission checker. RT-24's merged-tree source-completeness experiment addresses part of that boundary. |

The evidence supports independent typed admission checking when a graph may arrive from an untrusted or alternate producer. It also shows that source rebuild/completeness is a separate layer; graph validation cannot detect a declaration that never entered the graph.

## Current-main reproduction

The experiment reads stored instruction trees, reconstructs call uses, checks selected operation/interface/contract values and bindings, and requires declared dependency edges to match the owner and all referenced targets. It preserves call order and multiplicity in the body/reference vector. Recursive exact-reference groups and runtime termination are outside this checker profile.

Command from `research/PROTOTYPES/DEPENDENCY-GRAPH-01`:

```sh
python -B -m unittest -v tests.test_spg_representation tests.test_spg_admission
```

CPython 3.12.14 result: **16 tests passed**. The admission suite demonstrates:

- compiler-produced graph is admitted and its observations match the oracle;
- internally rehashed wrong-result-type, bad argument type, missing/unused reference, invalid call position, malformed unchosen branch, and missing selected values/bindings are rejected;
- persistence alone admits the missing-edge call, which remains executable;
- an event outside a declared effect trace is admitted structurally, leaving behavioral contract conformance to separate evidence;
- exact recursive groups are rejected as unsupported by this checker profile.

Source SHA-256 values at the baseline:

- `src/spg_admission.py`: `052548b2741958aebd9e5cd6faffc7ca83dae41792db8fed8ea55b54669bae0e`
- `tests/test_spg_admission.py`: `016df7f85f5acddc348f03e24a971241ae67ddf2a9f68a006f30ce3f7d57037e`
- `tests/test_spg_representation.py`: `385a6fe2ffd5267a45760a1f9b460ec4a97bb1434faeff27a7cbe60283c58ea1`

## Boundaries and external dependencies

No external service or maintainer decision was needed for this recheck. Full implementation selection still depends on internal research: pin a versioned typed-graph schema, establish source inventory and lowering completeness, add recursive-group semantics, and measure representative graph-size and decode-resource limits. Contract conformance remains distinct from structural admission. The checker does not prove that the program source is correctly parsed or that effects, provenance, aliases, or external dependencies are complete.

This closes only the bounded recheck of DEP-009. It does not complete RT-06 dependency semantics or the §0.3 edge register.
