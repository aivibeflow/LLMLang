# RT-00 — DEP-005 Evidence Recheck (2026-11-23)

**Plan item:** §0.3, validate dependency edges as evidence accumulates  
**Edge:** DEP-005, RT-03 → RT-05 (`Constrains`)  
**Baseline:** `main` `3847617bbc48e6e8deb70dd58e6ccfacdf93c769`  
**Disposition:** Retain DEP-005 as a strong hypothesis with scoped experimental evidence. The recheck confirms that the current typed-SPG fixture distinguishes reordered observable effects. It does not establish completeness of the full LLMLang semantics or select a graph encoding.

## Claim and competing representation choices

DEP-005 says the representation must preserve distinctions that can change observable behavior. The narrow question is whether an implementation may canonicalize effectful operand order away when the scalar result and event set stay unchanged.

| Candidate representation rule | Expected behavior for the fixture | Assessment |
|---|---|---|
| Preserve child/source order for all operations | Distinct ordered traces stay distinct; pure commutative expressions may miss reuse | Conservative and supported by this fixture |
| Normalize only operations proven pure/commutative; retain explicit order for effects | Distinct traces stay distinct while some pure forms can share identity | Consistent with the evidence, but purity/effect analysis is outside this test |
| Treat operands or event traces as unordered sets | Swapped effects can collapse despite different observations | Falsified by the fixture |
| Preserve order in a separate sequencing/effect relation rather than child order | Could retain the same distinction | Not implemented or compared here |

This evidence rules out the set-based rule for the tested observable operations. It does not choose between the first, second, and fourth implementation strategies.

## Current-main recheck

The existing experiment source is [`RT-05-TYPED-SEMANTIC-PROGRAM-GRAPH.md`](../../semantic-representation/RT-05/RT-05-TYPED-SEMANTIC-PROGRAM-GRAPH.md), especially SPG-02, and the focused tests are `tests.test_spg_ordered_lowering` and `tests.test_spg_representation` in the Dependency Graph prototype.

Command, run from `research/PROTOTYPES/DEPENDENCY-GRAPH-01`:

```sh
python -B -m unittest -v tests.test_spg_ordered_lowering tests.test_spg_representation
```

Environment: CPython 3.12.14. Result: **16 tests passed**. The effect-order test evaluates two operands that both emit labels and add values. Swapping their order preserves the integer result and event set but reverses the trace; the trace oracle and changed-selection checks retain the distinction. Additional tests cover ordered arguments, lazy branches, trace multiplicity, and equivalence of two expression surfaces within the same closed fixture grammar.

Source identities at the baseline:

- `tests/test_spg_ordered_lowering.py`: SHA-256 `3d8260a30c4fc4f1fa14b862b1d08594dd7af71112a53fcf163deb93a94acbc2`
- `tests/test_spg_representation.py`: SHA-256 `385a6fe2ffd5267a45760a1f9b460ec4a97bb1434faeff27a7cbe60283c58ea1`
- `src/spg_representation.py`: SHA-256 `44c61db14a6b4bd467c85382174020216dacdb5749dfd436f162cd3e053e1517`

## Boundaries and next dependencies

The experiment uses hand-built program fixtures and two restricted expression surfaces. It is not a parser-to-graph completeness test, does not prove source-language evaluation order, and does not test concurrency, nondeterministic effects, exceptions, cleanup, or effect handlers generally. COR-09 and COR-11 provide separate scoped witnesses, but those results also have their own declared fixture boundaries.

No external service or maintainer decision was needed to rerun this edge. A full implementation choice still depends on a specified observation/effect model, source lowering and completeness evidence, and experiments that distinguish pure canonicalization from explicit sequencing relations. Keep DEP-005's current confidence label; edge-by-edge validation of the remaining map stays open.
