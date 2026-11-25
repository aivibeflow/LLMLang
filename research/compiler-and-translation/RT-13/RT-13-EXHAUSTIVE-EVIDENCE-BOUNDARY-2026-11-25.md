# RT-13 — When exhaustive tests discharge a preservation claim

A preservation claim names the exact source and candidate, the admitted input and environment, and the required observation. In an operational model that admits nondeterminism, the claim also needs the behavior of all relevant schedules, or a checked reduction that covers them. This study compares exhaustive testing, sampled evidence and proof for [PLAN §2.5](../../../PLAN.md#25-correctness-of-optimization-and-translation) and [#297](https://github.com/aivibeflow/LLMLang/issues/297).

Lean checks two general conditions. Agreement on a test list gives agreement on the domain when every admitted input occurs on the list and the compared values are the required observations. Agreement after projection lifts to the full claim only when projected equality implies full equality for the subjects on the requested domain. The proof can use an input-specific reflection property. A kernel-checked counterexample separately shows that covering every ordinary input with one selected schedule can miss a relevant schedule. All four declarations have empty axiom lists.

| Evidence route | Claim supported | Needed to extend the claim |
| --- | --- | --- |
| Samples, including seeded or property-based tests | Agreement of the executed rows and concrete counterexamples | Cover the remaining inputs, outcomes and observation fields, or prove a checked reduction. |
| Exact finite enumeration | Universal agreement under the declared closed finite domain, complete observation and trusted oracle | Bind the authentic artifacts and their evaluator. Establish that the declared domain covers all requested executions, including outcomes and environment. |
| Formal proof or independently checked certificate | The exact theorem under its recorded premises, checker and semantic model | Prove observational/source/target correspondence where the claim refers to other representations. Review the encoded requirements and assumptions separately. |

For example, one exhaustive check can support a claim about two finite pure functions when all their admitted inputs are reachable through the tested entry and the output is the complete requested observation. A compiler-wide universal rewrite claim, an unbounded recursion property, or an execution claim with unenumerated schedules needs a checked universal argument. A solver certificate can provide such an argument for a supported exact encoding. Finite successes cannot fill a separate mandate for checked proof or trusted authority.

## Discriminators

The experiment declares 32 addresses, two result scenarios and two schedules. It compares five candidate variants across four suites and three observation projections. The fixture models deterministic observations at an explicit input and schedule. It checks pointwise preservation for that schedule mapping. A refinement claim over sets of nondeterministic observations would instead enumerate all complete outcomes on both sides and check the requested inclusion.

| Suite and observation | Rows | Defect that passes |
| --- | ---: | --- |
| Whole domain, complete ordered observation | 128 | None |
| Whole domain, result only | 128 | Missing schedule effect and reordered effects |
| Whole domain, unordered effects | 128 | Reordered effects |
| Every ordinary input, one schedule, complete observation | 64 | Missing schedule effect |
| First eight addresses, complete observation | 32 | Boundary result at address 31 |
| Successful inputs only, complete observation | 64 | Error replaced by a return |

The unchanged candidate passes every route. Only the whole-domain check with complete observations discharges the full declared claim. Conservative withholding under narrower tests means the evidence remains usable for its actual scope. It carries no finding of a defect in the unchanged candidate.

The runner reconciles three archived reports by exact commit and digest. It reads the records without rerunning the historical executions. The [branch elimination study](../../formal-verification/RT-07/RT-07-IDENTICAL-BRANCH-GUARD-2026-11-25.md) shows 108 trace-only differences outside a final-value comparison. The [state/Result mutation comparison](RT-13-STATE-RESULT-MUTATION-COVERAGE-2026-11-25.md) covers explicit bounded and seeded corpora. The [signed-add symbolic replay](RT-13-LLVM-CHECKED-ADD-SYMBOLIC-2026-11-25.md) checks 20 Lean claims about exact LLVM expressions under recorded assumptions. The last record supplies model-level whole-domain results and leaves general source correspondence open. The distinction constrains the validation evidence reused downstream. [DEP-013 and DEP-014](../../research-management/RESEARCH-DEPENDENCY-MAP.md#3-directed-dependency-register)

## Reproduce

Use Git 2.56.1, CPython 3.12.14 and Lean 4.36.0 at `611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9`. Run from the repository root with commit `840258f39219be2a1cdb94f12e9afd18b47ed73d` present. The [ledger](EXHAUSTIVE-EVIDENCE-01/evidence.json) includes the full comparison by variant, named observation, scope and archive.

```sh
set -eu
fixture=research/compiler-and-translation/RT-13/EXHAUSTIVE-EVIDENCE-01
out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT
lean -DwarningAsError=true "$fixture/Coverage.lean" > "$out/axioms.txt"
cmp "$fixture/axioms.txt" "$out/axioms.txt"
LC_ALL=C python3 -B "$fixture/run.py" > "$out/evidence.json"
cmp "$fixture/evidence.json" "$out/evidence.json"
```
