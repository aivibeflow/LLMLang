# RT-32 — Lean embedding correspondence for effectful conditionals

An effectful condition produces observations before it selects a branch. This experiment compares a deep Lean interpreter, generated shallow Lean terms and a hybrid check over the same compiled SPG bodies. It extends the [call-free scalar correspondence study](RT-32-SPG-LEAN-OBSERVATION-BINDING-2026-11-24.md) for [PLAN §2.4](../../../PLAN.md#24-verified-spg-to-lean-pipeline-rt-32) and [#296](https://github.com/aivibeflow/LLMLang/issues/296).

The fragment has one integer argument, integer literals, addition, subtraction, emitted string events and conditionals over equality of integer expressions. Equality evaluates both expressions from left to right. Only the selected arm contributes its result and trace. Nested conditionals are admitted within the fuel limit. Calls and numbers of other kinds are outside the decoder. There is no connection to native integer overflow in this mathematical integer fragment.

| Embedding | Construction and check |
| --- | --- |
| Deep | Decode the structured JSON term into a typed expression and interpret it in Lean. Retain the complete result and trace. |
| Shallow | Generate a Lean function from integer input to observation using composition combinators. It executes without interpreting the source syntax at each invocation. |
| Hybrid | Check the exact structured payload decodes to its named deep term. Check the exact shallow definition equals the lowering of that term. Use the generic correspondence proof to obtain equality of complete observations for every integer. |

The generic lowering theorem uses structural induction over the typed term. The conditional case equates both guard operands first, then equates only the selected arm and preserves the ordered guard prefix. A second theorem lifts a checked structural JSON admission to equality of the deep and lowered observations. The kernel checks concrete decoded-shape equations and equality of the generated shallow functions. The observed axioms are `propext` and `Quot.sound`.

## Checked evidence and correspondence boundary

The archive-pinned compiler translates paired infix and prefix forms for 12 programs, whose structured SPG bodies and snapshot identities agree. Both source executions are checked against independent result and ordered-trace formulas on seven inputs per program. The generated Lean module checks both embeddings on each observation. It also kernel-checks a general correspondence statement for each exact structured SPG body.

| Check | Result |
| --- | ---: |
| Source program/input pairs, tested in both notations | 84 |
| Concrete deep and shallow checks in Lean | 168 |
| Exact structured JSON decodes and per-program correspondence statements | 12 each |
| Unsupported structured inputs refused | 4 |
| Wrong trace propositions refused | 2 |

Swapping the two guard effects or evaluating an additional branch changes the modeled trace while leaving the chosen result fixed. Lean refuses both false equalities. Decoder controls reject out-of-range argument positions, a Boolean literal in the integer fragment, a call form and an invalid condition.

The lowerer consumes a structured JSON value. The generator also embeds the exact stored JSON text, and Lean's runtime JSON parser checks that it matches the structured term used in each proof. All 16 positive and negative byte checks pass. The byte check uses Lean runtime parsing and canonical JSON comparison. The theorem begins at the structured term. Source compilation, byte parsing correctness and the general production SPG decoder remain explicit correspondence obligations. The archive experiment supplies finite source coverage rather than a source-language theorem.

Deep embedding supports reasoning over syntax and exact traces. Shallow definitions simplify direct use of Lean integer lemmas. The hybrid route supplies a checked link between source-owned structured inputs and generated Lean definitions at the cost of maintaining a decoder, an interpreter and a lowering proof. This evidence informs [DEP-182 and DEP-185](../../research-management/RESEARCH-DEPENDENCY-MAP.md#3-directed-dependency-register).

## Reproduce

Use Git 2.56.1, CPython 3.12.14 and Lean 4.36.0 at `611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9`. Run from the repository root with archive commit `d83457c273e5b755f76add4b0d59cdeeed02e37e` available. The [ledger](CONDITIONAL-EMBEDDINGS-01/evidence.json) contains exact source and SPG identities, observations, the generated module digest and axiom audit.

```sh
set -eu
fixture=research/formal-verification/RT-32/CONDITIONAL-EMBEDDINGS-01
out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT
lean -DwarningAsError=true "$fixture/Embedding.lean" > "$out/axioms.txt"
cmp "$fixture/axioms.txt" "$out/axioms.txt"
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > "$out/evidence.json"
cmp "$fixture/evidence.json" "$out/evidence.json"
```
