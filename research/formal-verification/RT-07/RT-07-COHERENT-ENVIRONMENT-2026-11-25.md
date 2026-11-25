# RT-07 — Coherent environmental observations and generation identity

The [single-read experiment](RT-07-EXPLICIT-ENVIRONMENT-BOUNDARY-2026-11-25.md) makes an observed POSIX input explicit. This experiment asks what extra evidence is needed when two reads are claimed to come from one environmental snapshot. It distinguishes a pair with one observed origin from a pair that happens to match a published value.

An environment publishes a totally ordered sequence of generations. Each publication supplies two Boolean fields as one immutable image. A reader can inspect an epoch, read the left field, read the right field, then inspect the epoch again. Each step observes the current generation in the declared order. The test compares all 1,024 five-generation timelines and 70 nondecreasing schedules per timeline. A coherent-origin policy requires that one generation supply the entire returned pair. A weaker coherent-value policy requires that the pair was published at some point within the request interval.

| Policy | Accepted | Accepted with mixed origins | Accepted with no published pair in the interval |
| --- | ---: | ---: | ---: |
| Independent current reads | 71,680 | 35,840 | 5,560 |
| Equal exact endpoint generations | 5,120 | 0 | 0 |
| Equal endpoint tokens modulo 2 | 38,912 | 19,456 | 2,808 |
| Equal endpoint tokens modulo 4 | 20,480 | 10,240 | 1,080 |
| Equal authoritative field origins | 35,840 | 0 | 0 |
| Read both fields from the generation pinned at entry | 71,680 | 0 | 0 |

If generations 0 through 3 hold `(0,0)` and generation 4 holds `(1,1)`, a left read at 0 and a right read at 4 return `(0,1)`. That value never appears in the history, while both finite tokens match across the request. Lean checks the modulo-4 witness and proves that equal exact endpoint generations force both intermediate reads to originate there, under the ordered-read assumption. It also proves that a token identifies the generation within a fixed quotient block. Only this latter theorem uses `propext`.

The endpoint rule uses exact nonreused identities and returns a refusal when a publication is detected. Field origins avoid this extra refusal when both reads actually use a single generation. This assumes the provider couples each origin tag to the returned field. A pinned read instead assumes immutable retention and returns the entry generation even if a newer image appears. Its retention and freshness requirements belong in the contract. Independent reads remain valid when the consumer asks for two timestamped observations with no coherence claim.

## Evidence boundary

Both native profiles produce all 71,680 expected rows, including mixed and pinned values, endpoint decisions and field-origin decisions. The C fixture executes the injected interleavings using immutable images. Concurrent publication, memory-order guarantees, multi-process lifetimes, retry progress, authentic generation tags and correspondence with a production LLMLang source/runtime are additional obligations. The upstream observation distinctions in [DEP-007](../../research-management/RESEARCH-DEPENDENCY-MAP.md#3-directed-dependency-register) constrain the profile. The runtime correspondence in [DEP-018](../../research-management/RESEARCH-DEPENDENCY-MAP.md#3-directed-dependency-register) would supply the publication and read premises.

## Reproduce

Use CPython 3.12.14, GCC Debian 14.2.0-19 on x86-64 Linux, and Lean 4.36.0 at commit `611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9`. The [ledger](COHERENT-ENVIRONMENT-01/evidence.json) records policy counts, concrete counterexamples and replay digests.

```sh
set -eu
fixture=research/formal-verification/RT-07/COHERENT-ENVIRONMENT-01
out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT
lean -DwarningAsError=true "$fixture/Environment.lean" > "$out/axioms.txt"
cmp "$fixture/axioms.txt" "$out/axioms.txt"
LC_ALL=C CC=gcc python3 -B "$fixture/run.py" > "$out/evidence.json"
cmp "$fixture/evidence.json" "$out/evidence.json"
```

[PLAN §2.1](../../../PLAN.md#21-formal-semantics-of-the-language) · [Issue #293](https://github.com/aivibeflow/LLMLang/issues/293)
