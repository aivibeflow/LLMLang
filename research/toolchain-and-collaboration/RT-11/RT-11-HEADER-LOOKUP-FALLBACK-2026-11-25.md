# RT-11 — Negative header dependencies and conservative rebuild

A compiler depfile can list exactly the header it opened and still leave a lookup dependency implicit. When search stops at the first match, earlier absent files affect which input is selected. This experiment connects the [scoped binding study](../../semantic-representation/RT-06/RT-06-SCOPED-BINDING-READ-DEPENDENCIES.md) to an actual GCC lookup for [PLAN §3.1 and §3.2](../../../PLAN.md#31-semantic-dependency-model), [#298](https://github.com/aivibeflow/LLMLang/issues/298) and [#299](https://github.com/aivibeflow/LLMLang/issues/299).

The source uses a header searched across three ordered directories. Each directory can lack the file or contain one of two exact payloads. GCC compiles all 27 states under all six search orders. Its `-MMD` depfile lists the source and the selected header for every successful build. It omits the earlier failed lookups. The 156 resulting executables and six missing-header diagnostics all agree with an independent ordered lookup model. System headers and compiler configuration are fixed for the fixture.

Lean checks that an exact list of earlier absences followed by the selected input determines the lookup result, that changing the remaining candidates cannot change the winner, and that the old winning file can remain present after an earlier input starts shadowing it. All three theorems use no axioms.

## Observed reuse and fallback

| Comparison | Count |
| --- | ---: |
| Base/request pairs with the same compiler search order | 4,212 |
| Reuses under a key that checks the previous winning file only | 1,404 |
| Of those, stale header-selection records | 312 |
| Of those, stale executable artifacts | 156 |
| Reuses with the exact lookup prefix and selected bytes | 1,092 |
| Stale selections or executable artifacts with exact lookup evidence | 0 |

For example, the compiler first reads `c/llmlang_probe_choice.h` with value 0. Adding a file with value 1 in earlier directory `b` leaves the old depfile entry's bytes unchanged. The same build command now selects `b` and its result changes. If the new header instead has the old header's value, the native artifact can stay equal while the recorded selected input still changes.

The runner also varies which directories have authoritative presence or absence evidence. It compares all 33,696 availability cases. Reuse succeeds 4,116 times with the complete unchanged prefix. The policy rebuilds 9,816 times after a verified prefix change and 19,764 times when a required prefix observation is unavailable. Among the unavailable cases, 984 would wrongly reuse an artifact if the prior positive-only rule were used. A directory after the selected header can remain unknown if every earlier absence and the selected file itself are verified.

The candidate fallback is a fresh execution when a required lookup fact remains unknown. A later cache receipt needs complete lookup evidence for one observed filesystem snapshot. A missing file can contribute a proven negative input, while a failed observation leaves the input unknown. This fixture compares rebuild outcomes from its complete set of native runs. It does not measure fallback latency. General preprocessor discovery, filesystem coherence during extraction, implicit environment inputs and arbitrary header parsing remain further work. [DEP-010 and DEP-011](../../research-management/RESEARCH-DEPENDENCY-MAP.md#3-directed-dependency-register)

## Reproduce

Use CPython 3.12.14, GCC Debian 14.2.0-19 on x86-64 Linux, and Lean 4.36.0 at `611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9`. Run from the repository root. The [ledger](HEADER-LOOKUP-FALLBACK-01/evidence.json) records the native result digest, policy counts and an exact failure witness.

```sh
set -eu
fixture=research/toolchain-and-collaboration/RT-11/HEADER-LOOKUP-FALLBACK-01
out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT
lean -DwarningAsError=true "$fixture/Lookup.lean" > "$out/axioms.txt"
cmp "$fixture/axioms.txt" "$out/axioms.txt"
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > "$out/evidence.json"
cmp "$fixture/evidence.json" "$out/evidence.json"
```
