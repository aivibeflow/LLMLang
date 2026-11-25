# RT-13 — Common-subset backend delivery and evidence

The implementation gate asks for two backends that realize the same subset. Four existing emitter studies and the direct LLVM route cover this gate for the checked integer fixture. The audit pins their common source and native observation harness and verifies the archived evidence across all selected profiles. The branch baseline is `9390dabb68b38eea319e4f84ee544009ad8b308f`. [Backend selection issue](https://github.com/aivibeflow/LLMLang/issues/329)

The common fixture includes 64 typed programs, with 16 operations in four operand layouts and 3,085 vectors per program. It compares status, the final output slot and ordered callback values against a shared reference evaluator. The audit reads the four ledgers and verifies the hashes of the production fixture inputs and each emitter against the current branch. It also checks exact profile inventories, observation counts and status histograms. [Common typed fixture](../PROTOTYPES/LLVM-PRESERVATION-01/integer_fixture.py) · [Native comparison harness](../PROTOTYPES/LLVM-PRESERVATION-01/llvm_integer_probe.py)

| Backend group | Archived profiles | Matched observations per profile |
|---|---:|---:|
| C++ | 4 | 197,440 |
| Go | 2 | 197,440 |
| Java | 2 | 197,440 |
| Rust and direct LLVM | 4 | 197,440 |

The same source and comparison harness hashes appear in all four ledgers. The twelve profiles account for 2,369,280 archived observations. Those studies compare exact rows. This audit verifies the common input and recorded coverage without recompiling the profiles. [Audit receipt and exact source hashes](COMMON-BACKEND-RECEIPTS-01/evidence.json) · [C++ results](RT-13-GENERATED-CPP-INTEGER-LOWERING-2026-11-24.md) · [Go results](RT-13-GENERATED-GO-INTEGER-LOWERING-2026-11-24.md) · [Java results](RT-13-GENERATED-JAVA-INTEGER-LOWERING-2026-11-24.md) · [Rust and LLVM results](RT-13-GENERATED-RUST-INTEGER-LOWERING-2026-11-24.md)

The gate is met for this shared scalar subset. The record keeps each compiler, artifact and packaging scope in its original report. General executable semantics, complete effects and resource coverage, representative performance and normative backend selection remain open. [Translation and target backends](TRANSLATION-AND-TARGET-BACKENDS.md)

## Reproduction

Use CPython 3.12.14. The audit returns the same receipt with hash seeds 1 and 2. The original reports specify the compiler versions and commands for native replay.

```bash
fixture=research/compiler-and-translation/RT-13/COMMON-BACKEND-RECEIPTS-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > /tmp/llmlang-rt13-common-backends.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt13-common-backends.json
```
