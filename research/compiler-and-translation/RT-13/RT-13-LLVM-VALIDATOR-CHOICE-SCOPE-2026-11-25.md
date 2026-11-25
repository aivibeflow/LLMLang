# RT-13 — LLVM validator scope and stability of nondeterministic choices

The [shared validator study](RT-13-ALIVE2-VELLVM-COVERAGE-2026-11-24.md), its [stock replay](RT-13-STOCK-ALIVE2-LLVM-EH-2026-11-24.md) and the [checked conversion study](RT-13-LLVM-F64-I64-LOWERING-2026-11-25.md) provide different evidence about the same LLVM modules. This audit reconciles three archived ledgers, reruns structural validation on the exact modules and adds a separate choice-stability discriminator for [PLAN §2.5](../../../PLAN.md#25-correctness-of-optimization-and-translation) and [#297](https://github.com/aivibeflow/LLMLang/issues/297).

| Route | Evidence in the archived and fresh comparisons |
| --- | --- |
| LLVM assembly plus `opt -passes=verify` | All five archived shared modules and the conversion module are structurally accepted in a fresh replay. This accepts modules that contain refuted source/target pairs. |
| Alive2 | The two archived shared ledgers agree on one valid pair, two refutations, and two unsupported cases. Both refuted pairs exit with status zero. The archived conversion run validates two lowerings, refutes two poisonous controls and reports two unsupported intrinsic uses. The parsed verdict and its exact pair determine the scope. |
| Extracted Vellvm interpreter | All 18 concrete shared assertions and the failing assertion control have matching archived outcomes across the two ledgers. The unsupported atomic/fence cases in Alive2 still have passing concrete Vellvm assertions. The archived floating-point comparison has two saturation cases with uninterpreted calls, and explicit poison observations at the incorrect conversion boundary. |
| Native differential testing | The archived guarded saturation route agrees on its tested native observations. In the fresh choice fixture two native profiles each confirm membership of 12 observed output values in permitted sets. These rows establish evidence for concrete executions. |

A passed concrete assertion can corroborate either an agreement or a negative control if it asserts the expected outcome of that control. For example, Vellvm's checks of explicit poison at the inclusive positive conversion bound agree with Alive2's counterexample. A structural pass, interpreter exit, or matching finite native corpus gives no substitute verdict for a validator's unsupported operation. The archive reconciliation reads and checks the exact past Alive2 and Vellvm records. The fresh executions use LLVM structural checks, Clang native builds and Lean.

## Choice stability

LLVM specifies that freezing poison chooses a value and uses that same value at each use of the result. Separate freeze instructions may choose independently. The fixture forms two bits from a frozen value and its negation, or from two separately frozen values. Each function preserves a supplied defined bit when the input has no poison. A third function chooses a fixed bit for the poison case. [LLVM 19.1.7 language reference](https://github.com/llvm/llvm-project/blob/llvmorg-19.1.7/llvm/docs/LangRef.rst#freeze-instruction)

| Case for the poison input | Allowed modeled output pairs |
| --- | --- |
| Two independent freezes | `00`, `01`, `10`, `11` |
| Shared freeze | `01`, `10` |
| Fixed false choice | `01` |

A target refines a source in this model when its output set is included in the source set at the same input. Sharing two independent choices is a strict refinement, as is selecting an allowed fixed value. Replacing one shared choice with two independent choices can introduce `00` and `11`. Both reverse directions have explicit Lean counterexamples. Four Lean declarations have empty axiom lists. The IR fixture and native observations exercise this model with defined and poison input branches. The Lean statements are about sets of choices and do not prove a general LLVM translation.

The combined evidence supports recording exact source/target identities, refinement direction, unsupported operations and the semantics of correlated choices before reusing LLVM validator results. Concurrent atomics, arbitrary intrinsic coverage and LLMLang-to-LLVM correspondence remain outside the result. The evidence distinctions apply to [DEP-014 and DEP-016](../../research-management/RESEARCH-DEPENDENCY-MAP.md#3-directed-dependency-register).

## Reproduce

Use Git 2.56.1, CPython 3.12.14, Debian LLVM 19.1.7, Clang Debian 19.1.7 (3+b1), and Lean 4.36.0 at `611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9`. Run from the repository root with archive commit `5cb0641ad4f250ecb8fcf8d1c62335d52cc016c3`. Set `LLVM_AS`, `OPT` and `CLANG` to the corresponding tools if they are outside the path. The [ledger](LLVM-CHOICE-REFINEMENT-01/evidence.json) records module hashes, verdict scopes, choice sets and refinement directions. It records native membership checks so the replay can accommodate an allowed arbitrary choice.

```sh
set -eu
fixture=research/compiler-and-translation/RT-13/LLVM-CHOICE-REFINEMENT-01
out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT
lean -DwarningAsError=true "$fixture/Choice.lean" > "$out/axioms.txt"
cmp "$fixture/axioms.txt" "$out/axioms.txt"
LC_ALL=C python3 -B "$fixture/run.py" > "$out/evidence.json"
cmp "$fixture/evidence.json" "$out/evidence.json"
```
