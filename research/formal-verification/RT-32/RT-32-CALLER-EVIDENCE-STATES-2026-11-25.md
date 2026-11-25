# RT-32 — Compositional caller proofs and exact discharge states

A caller theorem can be kernel-checked while it still depends on a callee contract. This study models its transition to a closed result for the exact active binding. It uses the [compiled admission](RT-32-COMPILED-CLAIM-ADMISSION-2026-11-24.md) and [SPG proof dependency](RT-32-SPG-PDG-OCCURRENCES-2026-11-25.md) boundaries for [PLAN §2.4](../../../PLAN.md#24-verified-spg-to-lean-pipeline-rt-32) and [#296](https://github.com/aivibeflow/LLMLang/issues/296).

The admitted caller invokes one late-bound provider whose proof requires one transitive obligation. The modular theorem fixes the caller, contract and assumed interface. The provider and transitive obligations additionally bind their active version and exact subject. Every result must match its theorem, imported proof context and toolchain. The model accepts a checked disposition only after a separate trust admission gate.

| Disposition | Publication rule |
| --- | --- |
| Pending | No usable exact local proof is available. |
| Conditional | The exact modular caller theorem checks, with one or more version-bound obligations outstanding. Retain their individual statuses. |
| Unknown or unsupported | Report the exact diagnostic for the relevant claim. The result supplies no discharge. |
| Rejected | The exact claim or receipt fails admission. An unapproved or differently scoped receipt leaves the current request pending. |
| Refuted | A checked negative result applies to the exact claim. |
| Conflict | Both checked positive and negative evidence match a single key. Withhold closure so the conflicting evidence can be examined. |
| Closed | The exact modular theorem and all required provider and transitive proofs check under the same active context. |

A timeout or unknown result for a later job leaves a still-applicable verified result available for that exact claim. A new snapshot, policy revocation, or changed import environment can make a previously admitted receipt inapplicable. Closure then requires a new current evaluation. Lean checks that mismatched version or import identity blocks discharge, that unknown evidence supplies no proof, and that a conditional theorem composes with its admitted provider contract premise. All four model declarations have empty axiom lists.

## Schedule and trust checks

The matrix varies nine statuses or mismatch conditions for each of three roles. The model closes exactly one of 729 rows. The schedule corpus exhausts all 5,040 orders of seven events, including an active provider switch, proof results for the two versions and a later unknown result. An independent set check agrees at every one of 35,280 prefixes.

| Comparison | Count |
| --- | ---: |
| Exact closed prefixes | 10,080 |
| False closures when combining positive receipts by role without scope | 4,704 |
| Genuine closures lost if a newer unknown job supersedes a checked receipt | 3,360 |

At one switch, the modular theorem is still applicable. Checking roles alone reuses both old receipts and incorrectly publishes a closed result. With explicit versions, the new request is conditional until both new proofs arrive. After they arrive, a later unknown result for the exact leaf does not change the already accepted data. Separate mutations to subject, version, contract, theorem, imports, checker version and approval all keep the caller conditional. A contradictory exact provider control reports a conflict.

## Trusted computing base

The candidate model trusts the admitted SPG-to-proof correspondence, exact requirement and provider identities, and an independently supplied dependency inventory. The Lean kernel checks the final proposition and its dependency summary. The compiled check needs an authorized issuer, exact bundle and imported context, declared toolchain and approved transitive axioms. A signature attests to a subject and bundle and cannot establish their proof meaning alone. The archived six-fixture replay includes two admitted compiled receipts and eight refusal results, including changed compiled context, a foreign axiom and a stale provider. This study checks that archived ledger digest and then independently verifies the state logic. [Core obligation corpus](RT-32-CORE-OBLIGATION-CORPUS-2026-11-25.md)

Actual authentication and production policy remain outside the finite state machine. Its assumption is that inputs marked admitted already passed the relevant checker and authority gates. The immutable exact identities in the fixture stand for the evidence a production service would verify. Atomic publication of an active snapshot, issuer governance and formal correspondence for broader SPG constructs remain open. [DEP-180 and DEP-190](../../research-management/RESEARCH-DEPENDENCY-MAP.md#3-directed-dependency-register)

## Reproduce

Use Git 2.56.1, CPython 3.12.14 and Lean 4.36.0 at `611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9`. Run from the repository root with archive commit `7871ded14f9e56ff855757b1fa91b8d4e2904c75` available. The [ledger](CALLER-EVIDENCE-STATES-01/evidence.json) includes the exact archived dispositions, schedule witnesses and trust controls.

```sh
set -eu
fixture=research/formal-verification/RT-32/CALLER-EVIDENCE-STATES-01
out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT
lean -DwarningAsError=true "$fixture/Discharge.lean" > "$out/axioms.txt"
cmp "$fixture/axioms.txt" "$out/axioms.txt"
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > "$out/evidence.json"
cmp "$fixture/evidence.json" "$out/evidence.json"
```
