# RT-10 — Conditional proof of exact read continuation

Which claim follows from a proof that a client appends each successful read, and which parts depend on the native boundary? The study checks an abstract continuation invariant and audits its premises against the pinned Linux vector-read fixture. The branch baseline is `d7e6137785cf930b77e49211df70c0f8b07d26e5`. [Native vector-read receipts](POSIX-READV-PROGRESS-01/evidence.json) · [Verification and trust boundaries](../../formal-verification/RT-36/RT-36-FORMAL-VERIFICATION-ASSUMPTIONS-AND-TRUST.md)

The abstract cursor contains recorded bytes and the remaining input. A successful step appends the supplied bytes and advances by the reported count. An admissible history requires every count to fit the remaining input and every supplied block to equal that exact-length input prefix. The native correspondence also requires that the selected descriptor refer to the intended stream, the operation realize the declared prefix, and the destination preserve previously recorded bytes. A checked completion claim needs the premise that input is exhausted.

The Lean kernel checks one-step conservation, conservation for an arbitrary finite admissible history, exact final recovery when nothing remains, and the identity of a zero-progress step. A counterexample supplies the right count with the wrong byte and changes the combined input. Four results use `propext`, and the counterexample uses no axioms. [Lean source](POSIX-READ-CONTINUATION-PROOF-01/Continuation.lean) · [Printed axioms](POSIX-READ-CONTINUATION-PROOF-01/axioms.txt)

The evidence audit pins the original native receipt and checks all 108 cases. Exact counts and observed prefixes satisfy the step premises in 104 successful calls. The other four are would-block observations with no progress. Both native continuation policies report counts 3 and 4 and leave the pipe empty. The offset-aware policy retains all seven bytes. The whole-vector retry overwrites the previous prefix. [Premise audit](POSIX-READ-CONTINUATION-PROOF-01/evidence.json)

The verified claim is conditional on the abstract step and its observation boundary. The native fixture supplies exact evidence for this small Linux schedule and these initialized buffers. A universal native claim needs compiler and ABI correspondence, stable source and destination ownership, complete effect observation, and a justified relation between terminal events and stream state. POSIX edition conformance, concurrent readers, interruptions and cancellation with partial progress remain open. [POSIX conformance issue](https://github.com/aivibeflow/LLMLang/issues/326)

## Reproduction

Lean v4.36.0 at commit `611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9` accepted the source with warnings treated as errors. CPython 3.12.14 reads the pinned native ledger and produced identical audit receipts with hash seeds 1 and 2.

```bash
fixture=research/runtime-and-systems/RT-10/POSIX-READ-CONTINUATION-PROOF-01
lean -DwarningAsError=true "$fixture/Continuation.lean" > /tmp/llmlang-rt10-read-proof-axioms.txt
cmp "$fixture/axioms.txt" /tmp/llmlang-rt10-read-proof-axioms.txt
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > /tmp/llmlang-rt10-read-proof.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt10-read-proof.json
```
