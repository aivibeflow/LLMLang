# Checked signed division through WebAssembly lowering

[GitHub #327](https://github.com/aivibeflow/LLMLang/issues/327) · 2026-11-25

The fixture translates a typed signed 32-bit quotient into WebAssembly. It separates result representation, guards for target traps and ordered effects at the host boundary. It exercises a pure source profile and a host-observed profile with an attempt event followed by a settlement event.

## Lowering and preservation

The source result is a pair of status and value. A zero divisor and signed minimum divided by minus one produce distinct error statuses. The effectful profile sends the input operands in the attempt and the resulting pair in the settlement. Both effects occur for error results too.

The emitter validates the source signature and error/effect inventory. It emits an outer zero-divisor guard and an inner overflow guard so `i32.div_s` only executes in its defined domain. A structural audit checks the actual Wasm branch count, signed division and import inventory. WABT 1.0.36 accepts the four emitted binaries in its default profile. It rejects all four with multi-value disabled. The effectful profile additionally requires the exact `host.audit` binding.

The independent JavaScript oracle classifies error cases and uses BigInt division for successful signed results. It compares the result pair and each ordered event over 5,041 input pairs in each of Node 22.23.5 and Node 24.22.3.

| Route | Observations per engine |
| --- | --- |
| Pure and guarded, no imports | All 5,041 result pairs agree. |
| Guarded with intended host binding | All 5,041 complete observations agree. |
| Raw instruction and unrestricted input | 72 traps replace typed errors and omit settlement. |
| Raw instruction with the declared domain restriction enforced before entry | All 4,969 admitted observations agree. The wrapper refuses 72 inputs before calling Wasm. |
| Raw instruction with a weakened domain check | The signed-overflow pair reaches Wasm and traps. |
| Guarded with reversed effects or a same-signature altered host binding | Each control preserves all result pairs and changes all 5,041 ordered traces. |
| Guarded with the audit import absent | Native instantiation fails with a link error. |

## Translation outcomes

Twelve controls per engine classify exact pure evaluation, guarded evaluation with the pinned host service, caller-approved restricted evaluation, unsupported required capabilities and unverified evidence. The candidate decision binds source, module, engine, capability profile, observation view, host binding and restriction. The exact restriction is a precondition on the raw implementation. A wrapper that checks only the zero divisor fails its domain evidence. An old approval, a changed module or provider and an accepted Wasm module with incorrect effects all remain unverified. Explicitly unavailable capabilities produce unsupported. An unknown capability produces unverified.

The fixture records evidence for one fixed instruction contract on two Node engines. Approval and verified receipt data are fixture inputs. The experiments leave general control flow, recursion, concurrency, thrown host exceptions, authenticated evidence and other Wasm consumers open.

## Replay

Use CPython 3.12, the WABT utilities and one executable for each Node major version listed above.

```sh
fixture=research/compiler-and-translation/RT-09/WASM-CHECKED-DIVISION-01
python "$fixture/run.py" --node /path/to/node22 --node /path/to/node24 \
  --output /tmp/rt09-wasm-division.json
cmp "$fixture/evidence.json" /tmp/rt09-wasm-division.json
```

Two full replays rebuilt the modules in fresh directories and produced identical [evidence ledgers](WASM-CHECKED-DIVISION-01/evidence.json).
