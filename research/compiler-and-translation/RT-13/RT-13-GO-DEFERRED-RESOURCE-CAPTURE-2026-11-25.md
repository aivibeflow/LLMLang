# RT-13 — Go language versions and deferred resource identity

Can the same generated Go source close a different set of resources when the declared language version changes? This fixture compares four ways of capturing handles for deferred cleanup. The branch baseline is `437a6bd61ef0785ce962365d7036723e3be7677e`. [Names and loop binding](../../language-design/RT-03/RESEARCH-SCENARIO-50-NAMES-IDENTIFIERS-AND-SCOPE.md) · [Go 1.22 language changes](https://go.dev/doc/go1.22#language)

Each fixture allocates zero through four real pipe readers, with stable logical IDs. The scheduling function registers one deferred close per handle and returns. The runner checks the order and result of every `Close` call and probes each reader's availability with `Stat` before cleaning up any remaining handles. The same Go 1.24.13 compiler builds the source with explicit Go 1.21 and 1.22 language modes, which the runner checks in the binary metadata. [Go defer rules](https://go.dev/ref/spec#Defer_statements) · [Fixture source](GO-DEFERRED-RESOURCE-CAPTURE-01/main.go)

| Capture strategy for four readers | Go 1.21 language mode | Go 1.22 language mode |
|---|---|---|
| Closure over a variable declared in the range clause | Attempts ID 4 four times, leaves 1–3 live | Closes 4, 3, 2, 1 |
| Closure over an existing variable assigned by the range clause | Attempts ID 4 four times, leaves 1–3 live | Same |
| Snapshot the selected handle into a fresh local | Closes 4, 3, 2, 1 | Same |
| Evaluate the handle as an argument to the deferred call | Closes 4, 3, 2, 1 | Same |

All 40 observations agree with the oracle. The reused-binding controls return `os.ErrClosed` after the first successful close of ID 4. Availability checks confirm the other readers are still live after the scheduling function returns. The declared-variable capture behavior changes across the language modes even though the compiler executable is the same. The direct-argument and snapshot forms preserve LIFO cleanup and exact identity in both modes. [Byte identities and all native observations](GO-DEFERRED-RESOURCE-CAPTURE-01/evidence.json)

This extends the [Go scalar backend evaluation](RT-13-GENERATED-GO-INTEGER-LOWERING-2026-11-24.md) with a scoped handle-lifetime case. A Go backend must bind the language mode and preserve the selected owner's identity when deferring cleanup. Panics, asynchronous tasks, partial acquisition, foreign library ownership, representative performance and overall target selection remain open. [Backend selection issue](https://github.com/aivibeflow/LLMLang/issues/329)

## Reproduction

Use Go 1.24.13 linux/amd64 and CPython 3.12.14. The official Go archive hash is recorded in the [native inference study](../../language-design/RT-04/RT-04-NATIVE-INFERENCE-BOUNDARIES-2026-11-25.md#reproduction). Hash seeds 1 and 2 yielded identical receipts.

```bash
fixture=research/compiler-and-translation/RT-13/GO-DEFERRED-RESOURCE-CAPTURE-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" --go /path/to/go --cache /tmp/llmlang-go-defer-cache > /tmp/llmlang-rt13-go-defer.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt13-go-defer.json
```
