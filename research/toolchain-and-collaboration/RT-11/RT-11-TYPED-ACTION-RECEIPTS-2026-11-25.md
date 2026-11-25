# RT-11 — Typed build actions and scoped test and proof receipts

This study checks role-sensitive build inputs and outputs with actual GCC, native execution and Lean runs. It extends [semantic, action and artifact identities](RT-11-SEMANTIC-ACTION-ARTIFACT-IDENTITIES-2026-11-25.md) and [six-stage invalidation](RT-11-SIX-STAGE-PROPAGATION-2026-11-25.md) for [PLAN §3.3](../../../PLAN.md#33-semantic-build-and-cache-graph) and [#300](https://github.com/aivibeflow/LLMLang/issues/300).

| Action kind | Ordered typed inputs | Output |
| --- | --- | --- |
| Compile | C source, GCC release and options, native target profile | Exact object bytes |
| Link | Driver object and body object in distinct roles, native toolchain profile | Exact executable bytes |
| Test | Exact executable and expected concrete input/output cases, execution profile | Observed outputs and test disposition |
| Proof | Executable subject, exact mathematical proposition and applicability premises, Lean and axiom policy | Exact checked declaration source digest and axiom transcript |

An action key binds the role, artifact kind and digest for every input, with the action's context. An artifact digest addresses raw bytes. The result envelope binds the request and the named output roles and content digests. Correct retrieval requires all three to agree. A test executes a freshly materialized copy of the typed executable input. The proof invokes Lean on the exact generated proposition and checks the recorded axiom policy. The proposition concerns the mathematical model. Its correspondence to the executable is scoped to the separately observed fixture behavior.

## Results

Five edit profiles produce 20 scoped results, with one additional common driver compilation. GCC and Lean check the actual commands. The 15 native test outputs all agree with their fixture. Lean checks the five exact theorem requests. The kernel proof concerns its stated proposition and modeled assumptions.

| Edit | Invalidated action keys |
| --- | --- |
| Replace `n+(1+1)` with `n+2` | Compile only. Its output object is byte-identical and the other inputs stay equal. |
| Change the provider to `n+3` | Compile, link, test and proof. |
| Change only the selected test cases | Test. |
| Change only the model bound premise and corresponding theorem request | Proof. |

Eleven negative controls are refused. Among them are an input with the same bytes under the wrong kind, missing or reversed inputs, a same-kind object assigned to the wrong link role, an output of the wrong type and altered output bytes. Changing the selected cases invalidates the earlier test receipt. Changing an executable subject or premise invalidates its proof receipt. Changing only the source-applicability declaration also blocks reuse of an unchanged Lean statement. A test receipt fails a proof lookup.

The typed request shape helps identify what was consumed and which claim was checked. Broader compiler dependency discovery, complete tool and platform closure, trusted remote admission, and formal source-to-binary correspondence remain separate obligations. This fixture uses a declared native toolchain profile and local outputs. [DEP-012 and DEP-183](../../research-management/RESEARCH-DEPENDENCY-MAP.md#3-directed-dependency-register)

## Reproduce

Use CPython 3.12.14, GCC Debian 14.2.0-19 on x86-64 Linux, and Lean 4.36.0 at `611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9`. The [ledger](TYPED-ACTION-RECEIPTS-01/evidence.json) records each action and artifact identity, changed keys and refusal disposition.

```sh
set -eu
fixture=research/toolchain-and-collaboration/RT-11/TYPED-ACTION-RECEIPTS-01
out=$(mktemp)
trap 'rm -f "$out"' EXIT
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > "$out"
cmp "$fixture/evidence.json" "$out"
```
