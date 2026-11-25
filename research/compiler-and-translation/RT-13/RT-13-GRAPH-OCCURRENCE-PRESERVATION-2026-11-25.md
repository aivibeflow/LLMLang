# RT-13 — Occurrence preservation under structural graph sharing

A semantic graph can store one node for two identical subtrees. Whether the shared node runs once or once per incoming occurrence is a language rule. This study checks that distinction against the [executable state/Result reference](../../formal-verification/RT-07/RT-07-STATE-RESULT-REFERENCE-ENTRY-2026-11-25.md) for [PLAN §2.5](../../../PLAN.md#25-correctness-of-optimization-and-translation) and [#297](https://github.com/aivibeflow/LLMLang/issues/297).

The fixture lowers a closed source tree to a topologically numbered directed acyclic graph. Identical typed subtrees use one representation node. Its meaning is an operation on the cell, evaluated when a control edge reaches the occurrence. A strict sequence performs both operations, including after a tagged error from the first. A Result sequence skips the later operation after error. A conditional with a fixed guard reaches only its selected edge. Evaluation preserves the payload, the cell, and the ordered read/write events.

| Required evidence for graph rewriting | Check in this fixture |
| --- | --- |
| Typed source and graph agree before the optimization | Graph reconstruction preserves every admitted tree and rejects six malformed graphs. |
| Representation identity is separate from behavior | A systematic topological renumbering preserves source reconstruction and evaluation. |
| Rewrite preserves observable semantics | Independent graph evaluation agrees with the source wire entry and the source small-step machine. |
| A formal target preserves the relevant source model | Lean checks that finite graph denotation equals denotation of the unfolded tree. The relation includes result payload, cell and ordered trace. |
| The proof binds the actual decoder and transformed artifact | The finite run pins four archived source files and records its digest. General correspondence from the production SPG decoder to the Lean definitions remains open. |

The Lean proof is an induction over unfolding fuel. A leaf uses the same atom denotation. Every resolved child contributes its function from input state to observation. The graph and unfolded tree apply those functions under the same sequencing rules. Two edges pointing to the same read node produce two read events under strict sequencing. The theorem checks the finite model under available fuel. Its axiom list contains `propext` and `Quot.sound`. The read control uses `propext`.

## Results

The corpus combines the 4,105 archived source trees with 500 trees in which both sides of the root are composite and share an operand. Both cell values are tested. All 9,210 observations agree across the graph, its renumbering, the source wire denotation and the source small-step machine. Of 4,605 graphs, 4,400 receive a different numeric representation under the renumbering.

| Alternative evaluation rule | Observations changed | Changes visible only in the trace |
| --- | ---: | ---: |
| Memoize returned value by node identity | 1,290 | 1,206 |
| Memoize returned value by node identity and input cell | 870 | 834 |

On a repeated read with no mutation, both memoization rules return the right value and suppress a read event. On a read followed by a write and then the same read, a node-only memo can return the old value. Adding the cell to the key still suppresses repeated effects. A cache of pure denotation functions is compatible with evaluation per occurrence. A cache of once-computed values needs a separate checked effect and state argument or explicit source-level sharing semantics.

The candidate graph format has closed syntax, bounded acyclic structure and one cell. It cannot establish preservation for recursive graphs, effects outside this model or external condition evaluation. Extending it to Lean as a verification target requires validation of the source and graph readers, binder and type identity, admitted fragments, and trace-profile correspondence for the exact rewritten artifact. These constraints inform [DEP-015 and DEP-016](../../research-management/RESEARCH-DEPENDENCY-MAP.md#3-directed-dependency-register).

## Reproduce

Use Git 2.56.1, CPython 3.12.14 and Lean 4.36.0 at `611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9`. Run from the repository root with archive commit `58c8de7873cd6996eb7be82e40eef09f49dc3c37` available. The [ledger](GRAPH-OCCURRENCE-01/evidence.json) stores the exact archive hashes, observations digest and counterexamples.

```sh
set -eu
fixture=research/compiler-and-translation/RT-13/GRAPH-OCCURRENCE-01
out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT
lean -DwarningAsError=true "$fixture/Graph.lean" > "$out/axioms.txt"
cmp "$fixture/axioms.txt" "$out/axioms.txt"
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > "$out/evidence.json"
cmp "$fixture/evidence.json" "$out/evidence.json"
```
