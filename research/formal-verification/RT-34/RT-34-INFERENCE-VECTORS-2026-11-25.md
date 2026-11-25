# RT-34 provisional resource inference comparison

**Date** 2026-11-25 · **Plan** §2.0, CX-19 · **Issue** [#412](https://github.com/aivibeflow/LLMLang/issues/412)

The comparison uses 14 small pointwise-budget cases derived from eight benchmark IDs. The subjects model summation, nested work, size-changing composition, foreign costs, bounded or empty domains, delayed work and mismatched observation scope. Each label is provisional. The same fixture encodes the abstract cost model and points the independently executed Lean kernel at the exact claims it generated. Independent human adjudication of the models and expected labels remains open.

| Vector | Checked comparison |
| --- | --- |
| A, manual budget plus verification condition | Three claims check unconditionally and one checks with a stipulated foreign summary. Six remain unknown and four are outside the supported scope. |
| B, restricted symbolic inference | Coefficient dominance proves three claims and supports one conditional result. Bounded witness search finds five concrete violations of proposed fixed pointwise bounds. One unknown provider and four scope controls abstain. |
| C, potential-based checking | Lean rechecks a hand-supplied FIFO potential certificate from the separate pilot. Automatic potential synthesis remains open. |
| D, checked symbolic evidence | Lean checks all nine eligible claims or counterexamples using the recorded expressions and witness inputs. Four unsupported queries and the missing provider carry no corresponding claim. |
| E, hybrid with a model generating candidates | Available rule-generated candidate and kernel steps exercise part of the boundary. Live model generation, cost and latency remain open. |
| F, finite observations | Four violations appear by size 12. Seven cases agree in this finite window, and three have no applicable observation. |

The threshold subject agrees with its proposed linear pointwise budget at every measured size 0–12. The symbolic model generates a valid violating input at size 33. Treating finite agreement as a proof would misclassify this case. The positive and negative judgments apply to fixed budget expressions. A concrete violation of such a budget leaves its asymptotic growth class a separate question.

A failed proof of the supplied upper bound stays unknown until independent evidence establishes a violation. The valid proof relative to a foreign summary stays conditional. Empty or finite models and an abstract-step budget applied to wall time lack the scope required for the requested unbounded claim.

This fixture covers a small arithmetic subset of the benchmark. The checker validates claims relative to the encoded semantics. Implementation correspondence, comparative timings, benchmark coverage, live model vectors and independent human label adjudication remain open. No vector is selected for production.

Reproduce with Lean 4.36.0 and Python from the repository root.

```bash
study=research/formal-verification/RT-34/INFERENCE-VECTORS-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two independent runs reproduced the results and reviewed axiom reports byte for byte.
