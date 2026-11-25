# RT-32 — Independent checks for generated arithmetic proof candidates

A generated proof route can use a Lean tactic, a reusable theorem, or SMT to classify a candidate before proof checking. This study compares those routes on the same ten typed linear-integer obligations. The obligations model a countdown's initialization, preservation, decrease and exit checks. The work extends the [generated countdown obligations](RT-32-COUNTDOWN-LOOP-OBLIGATIONS-2026-11-24.md) for [PLAN §2.4](../../../PLAN.md#24-verified-spg-to-lean-pipeline-rt-32) and [#296](https://github.com/aivibeflow/LLMLang/issues/296).

The fixture stores premises and conclusions as typed affine terms. It renders each obligation as an explicit Lean theorem and as an SMT query for a counterexample. Both SMT engines evaluate those exact queries. For a satisfiable query, an independent integer evaluator checks the witness against every premise and the negated conclusion. For an unsatisfiable query, the optional triage route proposes `omega` for the exact original Lean theorem. Checked status depends on the Lean result and its transitive axiom policy.

| Route | Closed the requested theorem | Other result |
| --- | ---: | --- |
| Lean `simp_all` | 3 | Did not close 7 |
| Lean `omega` | 6 | Rejected 4 false obligations |
| Apply a reusable Lean theorem | 6 | Rejected 4 incorrect applications |
| cvc5 and Z3 triage, then Lean | 6 | Each solver supplied four independently validated witnesses |
| Inject a declaration for the false proposition | 0 | Lean's theorem depends on the unapproved declaration |
| Insert `sorry` | 0 | Lean rejects the warning-as-error check |

The proof library proves countdown decrease, nonnegativity, transfer conservation, initialization and exit for general integer variables under explicit premises. Two stride instances reuse the same decrease theorem. The false controls keep a counter unchanged, omit the invariant from an exit proof, weaken the nonnegativity guard, or add one extra update. Three more obligations are within `omega`'s supported fragment than `simp_all` closes. Failure to find a proof with one tactic gives no counterexample diagnosis. SMT's witnesses supply that diagnosis within this fixture. The solver-assisted proof route independently reconstructs the actual proof in Lean and never grants status from the solver verdict alone.

This comparison uses deterministic proposal templates. An optional LLM may propose a proof body under the same exact-statement, kernel and axiom gates. A live selected-model evaluation and comparison of latency or proof-search cost are outside this study. The syntactic connection to the real LLMLang source and wider solver theories need explicit source and encoding correspondence. [DEP-180 and DEP-181](../../research-management/RESEARCH-DEPENDENCY-MAP.md#3-directed-dependency-register)

## Reproduce

Use CPython 3.12.14, cvc5 1.4.2 at `282d5e0`, Z3 4.13.3, and Lean 4.36.0 at `611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9`. Run from the repository root. The [ledger](PROOF-ROUTES-01/evidence.json) records generated theorem and SMT query digests, solver witnesses and checked axioms. Set `LEAN`, `CVC5` or `Z3` if the executable is outside the path.

```sh
set -eu
fixture=research/formal-verification/RT-32/PROOF-ROUTES-01
out=$(mktemp)
trap 'rm -f "$out"' EXIT
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > "$out"
cmp "$fixture/evidence.json" "$out"
```
