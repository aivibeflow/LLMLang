# RT-11 — Metadata reuse and ELF self-observation

A metadata-only change can preserve native execution while changing an exact artifact request. This experiment uses a non-allocated ELF metadata section and checks how the result depends on what the executing program may observe. It extends the [native source metadata study](RT-11-NATIVE-SOURCE-METADATA-REUSE-2026-11-25.md) for [PLAN §3.2](../../../PLAN.md#32-incremental-analysis-and-invalidation) and [#299](https://github.com/aivibeflow/LLMLang/issues/299).

A single compiled executable supports normal arithmetic and a separate self-inspection mode. GNU objcopy produces six files per optimization level with distinct equal-length payloads in a non-allocated `.note.llmlang` section. The runner decodes each file's ELF64 header, program headers and section names. It compares each loadable program header and the digest of its file bytes. The independent Python checksum over the entire file corroborates the checksum reported by the self-inspection mode, which reads `/proc/self/exe` directly.

| Comparison | O0 | O2 |
| --- | ---: | ---: |
| Metadata variants | 6 | 6 |
| Normal integer observations that agree with the oracle | 54 | 54 |
| Variant pairs with identical loadable segments and normal observations | 15 | 15 |
| Variant pairs with different exact file identities and self-inspection outputs | 15 | 15 |

The change is invisible to the normal arithmetic profile on all admitted fixture inputs. It is observable through the branch that reads the exact executable file. That branch has identical loaded instructions and data across all six variants. The selected runtime input permits it to examine bytes from outside the loaded segments.

An execution-only reuse receipt can bind the declared loaded-code observation and the exact invocation inputs for this fixture. A request for raw file bytes, provenance, the metadata payload, or self-inspection needs the artifact's full identity. A product can reuse the scoped execution result and regenerate artifact-specific evidence separately. A loader that consumes different headers or a runtime that reads its own file adds dependencies to that projection. The FNV checksum distinguishes observations in this finite corpus. SHA-256 binds the fixture files and sections.

The study covers x86-64 Linux, same-length non-allocated section additions and the declared invocation modes. Other section layouts, platform loaders, changes outside the fixture, and a general proof of projection completeness remain open. [DEP-012 and DEP-018](../../research-management/RESEARCH-DEPENDENCY-MAP.md#3-directed-dependency-register)

## Reproduce

Use CPython 3.12.14, GCC Debian 14.2.0-19 and GNU objcopy from GNU Binutils for Debian 2.44, with `/proc/self/exe` available. Run from the repository root. The [ledger](ELF-METADATA-REUSE-01/evidence.json) includes the exact artifact, load segment and metadata identities and self-inspection outputs.

```sh
set -eu
fixture=research/toolchain-and-collaboration/RT-11/ELF-METADATA-REUSE-01
out=$(mktemp)
trap 'rm -f "$out"' EXIT
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > "$out"
cmp "$fixture/evidence.json" "$out"
```
