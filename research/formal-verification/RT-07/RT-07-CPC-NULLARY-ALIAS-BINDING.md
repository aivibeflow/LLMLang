# RT-07 — Distinguish CPC declarations from nullary proof aliases

**Date** · 2026-11-21

**Baseline** · `f33a311`

**Status** · Bounded executable experiment for [Plan §2.3](../../../PLAN.md#23-lean-logos-smt-and-solver-integration)

## Question and alternatives

Can a proof contain solver-generated abbreviations while keeping the checked query bound to the exact expected constants? The pinned parser's name table retains both declarations and nullary definitions. A strict check rejects all extra name-table entries, including abbreviations. Dropping the table check and testing only the constant count and lookups can confuse a declared constant with an alias to a differently named constant.

| Candidate | Trade-off |
|---|---|
| Require a flat proof with the exact constant table | Small admission surface. Rejects proof-local aliases used by cvc5 to share common terms. |
| Allow extra name-table entries | Easy to implement. Count and lookup alone do not establish which names were actually declared. |
| Classify top-level roles before binding parsed constants | Supports disjoint nullary aliases while retaining exact declaration identity. Requires an explicit command profile and consistency checks against the pinned parser state. |

The fixture implements the third option. It classifies raw Int/Bool constant declarations, disjoint nullary definitions, and ordinary assumption or step commands. It rejects alternate declaration forms and parameterized macros. It compares the original constant names with the expected set, verifies retained names and count, and delegates exact sort and constant lookup to the existing binder. It obtains expanded assumptions from the parser. The classifier does not expand arbitrary proof terms. [Scenario 34](RESEARCH-SCENARIO-34-SOURCE-TO-QUERY-SEMANTIC-CORRESPONDENCE.md#76-qf_lia-admissibility-and-external-wirechecker-boundary)

## Controls

- A compound arithmetic assumption and its abbreviated form give identical parsed assumptions and bindings. The strict baseline rejects the abbreviated form because its alias adds a table entry.
- A nullary alias for a differently named constant can inhabit the lookup slot for the expected name without increasing the uninterpreted-constant count. The raw declaration check rejects it.
- Extra constants, duplicated or overlapping alias names, parameterized definitions, wrong sorts and alternate declaration forms all fail admission.

This supports a restricted alias profile for interoperability with solver output. It remains a binder experiment, independent of the existing flat source-bound refutation check and JSON transport. A complete proof path still needs exact expanded-assumption comparison, a valid Logos verdict, and a reviewed command profile. The checked fixtures do not establish parser implementation correctness or a universal theorem for definitions, rewrites, or shadowing.

## Reproduction

Use Lean 4.36.0 and the pinned Logos revision. From `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding` run:

```sh
lake build --fail-fast LLMLangLogosBinding
lake env lean -DwarningAsError=true --run CpcNullaryAliasesTests.lean
```

[Binding experiment](../../PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/CpcNullaryAliases.lean) · [Controls](../../PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/CpcNullaryAliasesTests.lean)
