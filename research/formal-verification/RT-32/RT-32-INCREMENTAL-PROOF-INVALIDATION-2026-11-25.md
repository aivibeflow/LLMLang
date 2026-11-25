# RT-32 — Incremental invalidation of modular and closed proof evidence

A modular caller theorem can survive replacement of a provider while its conditionally imported contract holds. A closed result needs fresh evidence for the exact current dependency closure. This experiment freshly replays the [generated SPG call proofs](RT-32-GENERATED-CALL-CONTRACTS-2026-11-24.md) and [transitive closure fixture](RT-32-TRANSITIVE-PROOF-CLOSURE-2026-11-24.md), then varies the identities and dispositions their evidence consumes. [PLAN §2.4](../../../PLAN.md#24-verified-spg-to-lean-pipeline-rt-32) · [Issue #296](https://github.com/aivibeflow/LLMLang/issues/296)

## Exact replay

Git archive fixes the generated caller experiment, its SPG implementation and the transitive closure comparison. The runner regenerates the source-derived Lean modules, rechecks the generated statements in the exact Lean kernel, and compares the generated ledger byte for byte. It also recomputes the transitive closure comparison on all 12,288 root cases. These are fresh runs from archived inputs.

| Change in generated SPG | Caller evidence | Closed evidence |
| --- | --- | --- |
| Late rebind under the same ordered-effect contract | Same caller proof source and checked modular result | New provider and closure source. The previous provider identity is refused. |
| Directly pinned provider implementation edit | New caller proof source as well as new provider source | New closed proof source. |
| Rebind to the provider with reversed effects | The conditional theorem still checks | Closure fails the provider obligation. |
| Broaden the assumed trace contract | The changed generated caller proof fails | No closed proof is reported. |

The existing generated theorem checks an ordered-trace property for all admitted integer arguments. Its arithmetic and observed trace comparison on 35 executions remains finite. The transitive archive also replaces one receipt artifact in a diamond and checks that the closed digest changes.

## Invalidation matrix

The new matrix varies twelve explicit fields around the archived late and direct baseline cases. Seven fields describe the modular theorem's subject, caller and assumed callee contracts, premise, generator, Lean version and evidence artifact. A direct pin also includes its provider. The closed receipt adds the snapshot, selected provider, provider receipt and transitive receipt identities. A pending transitive premise independently blocks the closed state. Fields identify evidence in this fixture and can be checked at admission even when a cache lookup begins with a smaller request key.

| Per-mode check | Late binding | Direct pin |
| --- | ---: | ---: |
| Change profiles compared | 4,096 | 4,096 |
| Exact modular evidence hits | 32 | 16 |
| Retained modular evidence without a closed hit | 31 | 15 |
| Exact closed evidence hits | 1 | 1 |
| False closed hits if modular success suffices | 31 | 15 |

The digest policies and independent field-by-field check agree for all 8,192 change profiles. Single-factor controls falsely close one profile per mode when the gate omits the exact proof artifact, Lean identity, transitive artifact, or pending disposition. These four failures also have a small evidence pattern that isolates the missing gate. A provider's own receipt can retain its identity while a descendant is refreshed. The root closed receipt must still include the refreshed descendant or obtain a new independently checked closure proof.

The exact cache policy here separates pending or conditional evidence from fully justified evidence. It can conservatively request a fresh receipt after a semantically irrelevant artifact change. A future scope-equivalence policy could reuse proof checking across that change once it proves the relevant correspondence and records a new exact closure. Production source extraction, cryptographic admission, imported theorem trust policy, and persistence under concurrent publication remain open. The matrix mutates toolchain and artifact identities as controlled receipt inputs. It freshly runs one actual Lean revision. [DEP-183 and DEP-189](../../research-management/RESEARCH-DEPENDENCY-MAP.md#3-directed-dependency-register)

## Reproduce

Use Git 2.56.1, CPython 3.12.14 and Lean 4.36.0 at `611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9`, available through an Elan `lean +leanprover/lean4:v4.36.0` invocation. Run from the repository root with archive commit `cd95185e445ed247cfc06bf454977d836ab38d44`. The [ledger](INCREMENTAL-PROOF-01/evidence.json) records exact archive hashes and per-mode results.

```sh
set -eu
fixture=research/formal-verification/RT-32/INCREMENTAL-PROOF-01
out=$(mktemp)
trap 'rm -f "$out"' EXIT
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > "$out"
cmp "$fixture/evidence.json" "$out"
```
