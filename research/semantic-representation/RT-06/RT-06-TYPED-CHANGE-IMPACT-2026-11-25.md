# RT-06 — Impact planning across requirement, design and execution changes

A version change needs a plan for the actions that consumed the old version. This study checks impact discovery and action selection across five kinds of edits using the pinned LLMLang semantic store and change-impact planner. It extends [typed dependency closures](RT-06-DEPENDENCY-ROLE-CLOSURE-2026-11-25.md) and [impact planning benchmarks](RT-06-IMPACT-PLANNING-BENCHMARK-2026-11-25.md) for [PLAN §3.1](../../../PLAN.md#31-semantic-dependency-model) and [#298](https://github.com/aivibeflow/LLMLang/issues/298).

The fixture records requirement, contract, design, implementation and target artifacts as independently versioned inputs. Derived subjects include requirement-to-contract adequacy, design obligations, generated tests, executable build, an abstract model proof and target validation. Each derived subject has only the declared typed edges to the exact inputs it consumes. A change in one input triggers the reverse dependent closure. Independently reconstructing the complete candidate checks which immutable identities actually change.

| Edited input | Checked dependent scope in this fixture |
| --- | --- |
| Requirement | Human review of the new meaning and rederivation of the adequacy model. The existing contract, implementation and compiled bytes can retain their identities while applicability to the requirement needs review. |
| Contract | Recheck adequacy and design obligations, regenerate tests, and update affected model and native validation evidence. Standalone executable identity is independent of this contract in the fixture. |
| Design | Recheck the derived design obligation and regenerate the dependent test suite. Native validation consumes that suite. |
| Implementation | Rebuild the artifacts, run tests, and refresh both model and native evidence tied to the implementation. |
| Target | Rebuild and validate the target-specific result. The separate mathematical proof consumes no target configuration. |

The completeness audit binds the baseline and exact edge scope. The planner checks validity of that binding before allowing the compact action plan. An authoritative completeness inventory is a prerequisite for the fixture's positive evidence. Generating a typed inbound edge digest from a closed graph does not establish that a production extractor found every edge.

## Results

All 992 ordered nonidentity transitions between 32 versions match independent candidate reconstruction. The pinned planner schedules all 8,896 expected typed actions with matching subjects. For every transition, both a missing audit and an audit bound to the wrong snapshot require human review and full revalidation. The unresolved plan receives its own identity.

The useful reuse route here is to retain an immutable artifact when its actual inputs remain equal while refreshing evidence that consumes another changed input. An alternative uses complete revalidation when the dependency inventory cannot support the narrower plan. This study compares identities and planning outcomes. It leaves normative contract adequacy, general source-to-graph extraction, authorization of audits, action execution, and coherent publication to their own evidence. [DEP-011 and DEP-029](../../research-management/RESEARCH-DEPENDENCY-MAP.md#3-directed-dependency-register)

## Reproduce

Use Git 2.56.1 and CPython 3.12.14 from the repository root with archive commit `c1da4dc2753bc3db390f80e0643db911ce870e2c`. The [ledger](TYPED-CHANGE-IMPACT-01/evidence.json) records the exact planner and store digests, single-axis cases and the digest of every planned transition.

```sh
set -eu
fixture=research/semantic-representation/RT-06/TYPED-CHANGE-IMPACT-01
out=$(mktemp)
trap 'rm -f "$out"' EXIT
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > "$out"
cmp "$fixture/evidence.json" "$out"
```
