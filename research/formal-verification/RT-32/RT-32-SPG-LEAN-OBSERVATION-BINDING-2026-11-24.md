# Binding Lean observations to exact SPG bodies

- **Date:** 2026-11-24
- **Research:** RT-32, RT-03, RT-05 and RT-09; PLAN §2.4
- **Baseline:** `4da3fea5f21b851e385286ecbedd7d8ce378166f`
- **Evidence:** A generic lowering theorem, two exact body and contract certificates, four observation paths and adversarial controls

A shallow Lean function can preserve every returned value and reverse two effects. In both fixtures, Lean proves the return equality for all integer inputs. At zero the altered function emits `right` before `left`. The altered trace can satisfy a contract that permits either order. Source correspondence still rejects that execution for the original SPG body.

## Admitted profile and checks

The fixture takes one `Int` argument and returns an `Int`. It admits signed 32-bit integer literals, Boolean literals, integer addition and equality, lazy branches and ordered output labels. Values and intermediate arithmetic use mathematical integers. Each body evaluates its guard once and emits `prepare` and `test`. The true branch emits `left` then `right` while computing the sum. The false branch emits `fallback` and adds a constant. The two bodies differ in that constant, using `2` and `-2147483648`.

The existing SPG compiler publishes the body and links its trace contract. The fixture reads the exact stored body and contract and emits a typed Lean syntax witness and a shallow function. The Lean kernel checks two separate equalities, reconstructing the canonical body and contract bytes from their Lean representations. A theorem by structural induction checks that lowering the typed syntax to shallow functions preserves the complete observation for every integer input. For each generated shallow function the kernel checks its equality with this lowering and discharges its declared trace contract for all inputs.

| Candidate | Checked property | Remaining boundary |
| --- | --- | --- |
| Shallow function | Compact expression for the concrete contract proof. A return-only theorem accepts the reordered implementation. | Equivalence to the selected SPG body requires a separate check. |
| Deep typed syntax and evaluator | Encodes the original ordering and supports a generic proof by induction. | Exact body and contract anchors must come from the chosen SPG snapshot. |
| Hybrid with exact bytes and a lowering theorem | Binds both artifacts for two implementations, then checks the generated shallow observation and trace contract for all inputs. | The SPG reader and correspondence of the Python and Lean semantics remain in the trust boundary of the source claim. |

The direct SPG interpreter, the ordered-instruction interpreter, the deep Lean evaluator and the generated shallow function agree on 14 observations over the two exact bodies. Each body is checked at zero and both sides of zero, across the signed 32-bit range and at `±2^96`. For each body, Lean rejects the reordered candidate's claimed trace equality, the reordered typed witness's claimed round trip to the original bytes, and an order-only substitution for its trace contract. The profile also rejects subtraction, which the SPG compiler supports.

## Reproduction and scope

The [replay](../../PROTOTYPES/DEPENDENCY-GRAPH-01/spg_lean/replay.py) uses Lean 4.36.0 (`611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9`) and Python 3.12.14. The [ledger](../../PROTOTYPES/DEPENDENCY-GRAPH-01/spg_lean/results.json) records the exact snapshots, definition and contract hashes, ordered artifacts, generated Lean module hashes, observations, and axiom output. The generic theorem and the two program certificates use standard Lean axioms. The byte equalities use `propext`.

```sh
fixture=research/PROTOTYPES/DEPENDENCY-GRAPH-01/spg_lean
replay=$(mktemp)
python3 -B "$fixture/replay.py" --output "$replay"
cmp "$fixture/results.json" "$replay"
```

The kernel checks the typed Lean syntax and the supplied canonical bytes. Source parsing, SPG extraction and the Python interpreter remain outside the kernel proof. The finite cross-check tests that boundary, and the general theorem covers the Lean evaluator-to-shallow boundary. Recursion, loops, calls, staged failure, ownership and deployed artifact admission have separate obligations. This experiment checks termination by structural recursion on the admitted finite expression and the two exact trace contracts. It leaves the broader embedding selection open.
