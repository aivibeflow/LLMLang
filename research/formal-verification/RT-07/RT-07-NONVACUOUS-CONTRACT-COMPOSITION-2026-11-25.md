# RT-07 — Per-branch coverage in contract composition

The [sequential handoff](RT-07-SEQUENTIAL-CONTRACT-COMPOSITION-2026-11-25.md) and [tagged recovery](RT-07-RECOVERY-CONTRACT-COMPOSITION-2026-11-25.md) studies require that each allowed continuation receives an admissible input. This study adds the local obligation that an admitted continuation has behavior in the declared model. It checks whether a nonempty composed outcome set or a universal postcondition can hide a missing branch.

Write each prefix observation as either an explicit stop or a handoff with state. A stop preserves its outcome and effects. At a handoff, require the successor precondition on the post-prefix state and append its effects after the prefix. Coverage requires at least one prefix outcome and at least one successor outcome for **every** reached handoff. A row at an input outside the successor precondition supplies no coverage. Explicit error, cancellation and divergence are declared observations and can supply coverage. A claim of successful or finite termination needs separate obligations on those tags.

Lean proves that a covered composition has an outcome, and that a contract-level admissibility guard together with evidence on the successor's admitted inputs covers every handoff of a refining prefix. The proof requires that the refining prefix itself has an outcome. It also checks a counterexample where an explicit stop reaches the composed set while another allowed prefix branch has no continuation. All three statements have empty axiom lists. The Lean composition theorem uses an abstract outcome type and does not model trace concatenation. The finite runner checks ordered prefixes on the concrete branch model.

## Bounded comparison

The test varies every subset of five prefix outcomes, every subset of four possible outcomes at each of two successor states, and each of four successor domains. An independent bitset coverage rule agrees with the path-based evaluator in all 32,768 cases.

| Check | Count |
| --- | ---: |
| Declared prefix and all handoffs covered | 16,648 |
| Covered with no possible normal return | 11,144 |
| Uncovered composition with a nonempty outcome set | 13,719 |
| Uncovered composition where every handoff is in the successor domain | 1,784 |
| Uncovered composition that passes a universal no-error-tag check | 7,484 |
| Empty outcome set that vacuously passes the same check | 2,401 |

For example, a prefix may fail explicitly or succeed at state 0. If the successor has no declared outcome at state 0, the composite contains the prefix error and still has a coverage gap. If the sole successor outcome is explicit divergence, the branch is covered, with divergence ordered after the successful prefix. A successor return row cannot fill a gap when the successor declares that input inadmissible.

A relational proof of inclusion can use a known exact behavior set. A reusable contract composition additionally needs a checked coverage argument for declarations, or a narrower checked reachability claim to remove obligations on ruled-out handoffs. A declaration with outcomes can still be unimplemented. Native correspondence, full traces for infinite runs, asynchronous cleanup and authority to accept the contract remain open. This result informs the formal contract evidence boundary in [DEP-007 and DEP-022](../../research-management/RESEARCH-DEPENDENCY-MAP.md#3-directed-dependency-register).

## Reproduce

Run from the repository root with CPython 3.12.14 and Lean 4.36.0 at `611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9`. The [ledger](NONVACUOUS-CONTRACTS-01/evidence.json) records witnesses, counts and a digest that includes both the exact composed observations and the missing branches.

```sh
set -eu
fixture=research/formal-verification/RT-07/NONVACUOUS-CONTRACTS-01
out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT
lean -DwarningAsError=true "$fixture/Compose.lean" > "$out/axioms.txt"
cmp "$fixture/axioms.txt" "$out/axioms.txt"
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > "$out/evidence.json"
cmp "$fixture/evidence.json" "$out/evidence.json"
```

[PLAN §2.1](../../../PLAN.md#21-formal-semantics-of-the-language) · [Issue #293](https://github.com/aivibeflow/LLMLang/issues/293)
