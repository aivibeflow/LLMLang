# RT-34 loop, mutual recursion and provider cost correspondence

**Date** 2026-11-25 · **Plan** §2.0, CX-04–07 · **Issue** [#412](https://github.com/aivibeflow/LLMLang/issues/412)

A bounded generator accepts one typed control shape. A loop invokes each size `i` from 1 through `n`. Two mutually recursive functions alternately take a provider step and recurse on `i − 1`, terminating at zero. Two separately compiled provider objects expose the same functional behavior with distinct weights for one branch. The cost projection observes the return value, each provider's visit count, and weighted expense. The independent oracle constructs the visits directly from loop size and parity.

| Evidence | Checked result |
| --- | --- |
| Native comparison | Sixteen GCC builds across two optimization levels, two provider profiles and four source modes produce 1,056 observations at sizes 0–32. Every declared source observation matches the independent oracle. |
| Correspondence controls | Omitting the last outer iteration changes 64 returns in each build. An extra provider call and a wrong provider each preserve all returns yet change weighted costs in 63 cells per build. A zero recursive decrement is refused before code generation. |
| Symbolic recurrence | Lean proves each alternating call chain costs at most `cap × i` when both provider rates are at most `cap`. Positive size decreases structurally. Summing over the loop yields `cap × triangular(n)`. Unit rates give exact call counts. |
| Provider rebinding | The caller object stays byte-identical. The expensive provider exceeds the old cap-five bound in 57 cells per optimization level, while an exact cap-nine receipt applies to the new provider. |
| Evidence closure | The pilot graph binds exact generated source, caller, executable, finite observations, recurrence proof and provider artifact. All four omitted-node controls and reuse of the old graph after rebinding are refused. Reversing record order preserves the complete graph. |

Five Lean propositions check the abstract recurrence and the old-budget counterexample. The axioms reported are a subset of `propext` and `Quot.sound`. The finite translation check and abstract recurrence remain explicitly scoped in the composed graph. The instrumented units are model costs. A general source correspondence theorem, SPG or PDG schema, higher-order closure analysis, actual timing and independent benchmark adjudication remain open.

Reproduce with GCC and Lean 4.36.0 from the repository root.

```bash
study=research/formal-verification/RT-34/LOOP-CALL-CORRESPONDENCE-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two independent builds and proof runs produced byte-identical ledgers.
