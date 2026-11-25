# RT-06 — Dependency roles and exact action closures

Execution, verification and source audit consume different parts of a semantic graph. This study checks the corresponding transitive closures through the pinned LLMLang content store. It extends the [typed identity projection comparison](../RT-05/RT-05-TYPED-EDGE-PROJECTIONS-2026-11-25.md) for [PLAN §3.1](../../../PLAN.md#31-semantic-dependency-model) and [#298](https://github.com/aivibeflow/LLMLang/issues/298).

The fixture evaluates an exact provider at two inputs. The caller may return a note value in addition to the numerical result. Its source can carry one of two comment layouts. The verification action checks a bound and records the exact checker identity. The source audit returns exact presentation and note data with the associated semantic subject.

| Request | Identity and transitive inputs |
| --- | --- |
| Execute | Exact caller, exact provider and any note actually observed by that caller. |
| Verify | Exact implementation and its execution dependencies, plus requested contract and checker version. |
| Audit source | Exact implementation and its dependencies, exact source revision and reported note. |
| Navigate | Context-scoped reverse relations from the implementation to source, note and verification request. The implementation identity remains independent of those retrieval links. |

The same note can therefore be a descriptive relationship in one execution profile and a hash-relevant dependency in another. Lean checks that changing an unobserved note preserves the declared observation. When the note is observed, Lean proves that equality requires the consumed note to agree. Both theorems have empty axiom lists.

## Results

The runner varies seven binary coordinates over 128 profiles. It constructs three closures per profile from actual stored values and compares all 384 closure digests with independently enumerated member sets. All agree. The runner also checks that non-hash relations can be attached without changing the stored implementation subject.

| Key policy | Stale execution hits | Stale verification hits | Stale source-audit hits |
| --- | ---: | ---: | ---: |
| Separate typed requests | 0 | 0 | 0 |
| Use the runtime identity for every request | 0 | 576 | 512 |
| Exclude notes even when consumed by the runtime | 256 | 832 | 768 |

Across 8,128 unordered profile pairs, complete snapshot keys also avoid stale reuse and miss 704 safe execution cases, 128 verification cases and 192 source-audit cases. The typed keys retain every safe reuse seen in this fixture. A verifier change can leave the Boolean check result unchanged while changing which evidence was requested. A comment layout can change the audit record while leaving the ordinary implementation unchanged. A note read by the caller changes its actual observation even if the surrounding relation is labelled metadata.

The evidence supports hashing typed, actually consumed edges and following their closure for the requested action. Provenance, audit and traceability can refer to semantic subjects without automatically entering their execution identities. Such scoped reuse requires complete extraction of observed inputs and a faithful identity encoding. The fixed fixture supplies both the edge inventory and the observation model. Production extraction, identity policy, wider environment observations and formal correctness of the full store remain open. [DEP-009 and DEP-012](../../research-management/RESEARCH-DEPENDENCY-MAP.md#3-directed-dependency-register)

## Reproduce

Use Git 2.56.1, CPython 3.12.14 and Lean 4.36.0 at `611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9`. Run from the repository root with archive commit `e32fd0697dfeca50052593077d507ef38bb0b3a4` available. The [ledger](DEPENDENCY-ROLES-01/evidence.json) records the exact store source, projection counts, witnesses and comparison digest.

```sh
set -eu
fixture=research/semantic-representation/RT-06/DEPENDENCY-ROLES-01
out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT
lean -DwarningAsError=true "$fixture/Observation.lean" > "$out/axioms.txt"
cmp "$fixture/axioms.txt" "$out/axioms.txt"
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > "$out/evidence.json"
cmp "$fixture/evidence.json" "$out/evidence.json"
```
