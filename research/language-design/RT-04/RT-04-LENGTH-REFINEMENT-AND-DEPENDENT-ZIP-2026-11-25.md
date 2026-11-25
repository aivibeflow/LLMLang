# RT-04 — Local bounds, relational refinements and dependent lengths

Can a type or boundary check guarantee an exact pairwise zip without losing unmatched input? This fixture compares a local upper-bound refinement, a checked relation between the two input lengths and a type indexed by the declared length. The branch baseline is `d6c3209af1794ce89417e6f5753f35e8ac2aca59`. [Type-system alternatives](RT-04-TYPE-EFFECT-OWNERSHIP-AND-CAPABILITY-ALTERNATIVES.md)

| Interface | Evidence required | Result |
|---|---|---|
| Each list has length at most 4 | Two local bound proofs | A prefix zip can drop the tail of either input |
| Checked relational refinement | The two actual lengths are equal | Returns every position on success or rejects a mismatch |
| Two arguments with common length index `n` | A proof that each input has the same indexed length | Returns a list indexed by `n` |

The Lean model defines a sized list as a list paired with a proof of its length. Packaging raw data under an externally declared index succeeds exactly when that declaration matches the actual length. With a common index, the checked raw zip and indexed zip return the same pairs. The indexed construction preserves the output length. The kernel also checks a concrete one-element and two-element bounded counterexample. A positive example elaborates at matching indices, while an expected-failure control attempts to combine indices 1 and 2. [Lean source](LENGTH-REFINEMENT-01/Length.lean) · [Printed axioms](LENGTH-REFINEMENT-01/axioms.txt)

The executable comparison enumerates 961 ordered pairs of Boolean lists of lengths zero through four. Local bounds admit all of them, and prefix zip discards elements in 620. The relational check admits exactly the 341 equal-length pairs. The declared-index boundary checks five possible declarations for each pair, accepts 341 of 4,805 combinations and rejects every inconsistent declaration. Every admitted output preserves each expected pair. [Finite evidence](LENGTH-REFINEMENT-01/evidence.json)

The comparison supports using a shared length relation when an operation requires complete pairing. The runtime check places that obligation at the boundary. An indexed caller can carry the proof as part of its input and return a result with the same index. The fixture covers exact lengths and pure lists. Elaboration and proof ergonomics, representation erasure, effectful input, independent review and LLMLang type-system selection remain open. [Type and data model issue](https://github.com/aivibeflow/LLMLang/issues/324)

## Reproduction

Lean v4.36.0 at commit `611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9` accepted the file with warnings treated as errors. Two theorems are axiom-free, one uses `propext` and two use `propext` and `Quot.sound`. CPython 3.12.14 produced identical receipts with hash seeds 1 and 2.

```bash
fixture=research/language-design/RT-04/LENGTH-REFINEMENT-01
lean -DwarningAsError=true "$fixture/Length.lean" > /tmp/llmlang-rt04-length-axioms.txt
cmp "$fixture/axioms.txt" /tmp/llmlang-rt04-length-axioms.txt
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > /tmp/llmlang-rt04-length-refinement.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt04-length-refinement.json
```
