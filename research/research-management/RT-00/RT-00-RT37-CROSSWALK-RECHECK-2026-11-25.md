# RT-00 independent reconstruction of the RT-37 target-closure crosswalk

The original RT-37 crosswalk records seven fixture ledgers but leaves its Python version unspecified. This check reads its archived inputs at `7d407636c4a06d1b601376bc66ea96d5a26e0b8f` on `research/all` and independently derives the comparison ledger in JavaScript. The full result matches all 2415 archived bytes, including the input hashes. The [receipt](RT37-CROSSWALK-RECHECK-01/evidence.json) records the exact path, Git blob and SHA-256 for each input. [Original RT-37 study](../../runtime-and-systems/RT-37/RT-37-EXECUTION-CLOSURE-AND-ALLOCATION-PROFILES-2026-11-25.md) · [#284](https://github.com/aivibeflow/LLMLang/issues/284)

| Evidence slice | Reconstructed result |
| --- | --- |
| Cortex-M3 closure and startup | Five boot images have the same archived UART result. Recomputing file-backed load extents agreed for every image. Three startup controls retain the same section layout and change the UART result. |
| Cortex-M3 allocation | Four images agree on a 64-byte arena. The crosswalk counts 644 allocation cases and 2,704 recorded requests. |
| STM32 | Both profiles place the vector at the manifest's flash origin. The archived Renode traces match the six-row reference for each profile, and both profile ledgers preserve foreign-object and missing-member refusals. |
| ESP32 | The two freestanding architecture records carry zero runtime dependencies. The three SDK boot profiles preserve distinct machine and trace observations. The five optional radio archives belong to a static link-map observation. |

Four controls reject a changed flash extent, an equal-output startup control, a substituted emulator trace and a static-to-hardware radio claim. This reconstructs the crosswalk from existing results. It does not rerun the firmware, emulator or original Python program and leaves the historical Python version unresolved. The verification ran through the task's JavaScript runtime against GitHub Git data responses. The local Git/Node.js wrapper shares the same comparison logic and its command-line invocation remains unchecked while the shell is offline.

```sh
fixture=research/research-management/RT-00/RT37-CROSSWALK-RECHECK-01
out=$(mktemp)
node "$fixture/run.mjs" > "$out" && cmp "$fixture/evidence.json" "$out"
```
