# RT-13 typed constraints for implementation selection

A candidate can have a compatible operation and still require a different ABI, unavailable capability, or a performance guarantee supported only by evidence from another environment. The selection boundary consumes an exact candidate identity after discovery. It checks each kind of requirement using the relation its meaning calls for. The model separates a required bound from optional observations used for ranking. [Discovery and binding](RT-13-CATALOG-DISCOVERY-AND-BINDING-2026-11-25.md) · [Fallback](RT-13-IMPLEMENTATION-FALLBACK-2026-11-25.md)

| Input | Eligibility relation in the model |
| --- | --- |
| Target and ABI | Exact target-profile identity and ABI identity |
| Runtime and deployment | Exact runtime identity and deployment-profile identity |
| Granted capabilities | All capabilities required by the candidate appear in the grants |
| Requested features | All required features appear as offers of the candidate |
| Security evidence | Checked policy receipt for the exact artifact and accepted authority |
| Mandatory performance | Receipt for the exact artifact, required workload/environment and metric, with bound at most the requested maximum |
| Optional performance observations | Available for subsequent ranking under their stated scope |

An implementation that requires only a subset of the grants can qualify. Two sets that overlap can still leave an ungranted capability. The target, ABI, runtime and deployment labels name complete profiles. They stand for facts such as ISA baseline, object conventions, runtime version and configured deployment constraints. A cross-profile adapter can qualify under a new identity with its own evidence. The policy check assumes a verified receipt with an authority identity. It does not verify signatures or prove that a declared offer is enforced.

```mermaid
flowchart LR
    D["Discovered candidate and exact artifact"] --> P["Exact execution and deployment profiles"]
    P --> C["Required capability and feature inclusion"]
    C --> E["Checked evidence for artifact and authority"]
    E --> M["Mandatory metric, scope and bound when requested"]
    M --> R["Eligible for separate ranking"]
```

## Checked results

Lean checks that a wider set of grants preserves existing eligibility, that a mandatory bound requires a receipt matching artifact, scope and metric, and that each non-performance constraint follows from eligibility. All three theorems have no axioms. The proof treats measurement fields and eligibility claims as model inputs. [Lean model](SELECTION-CONSTRAINTS-01/Constraints.lean)

An independent label-based oracle agrees with all 4,200 decisions in the finite fixture. Each counterfactual changes one relation and retains the others.

| Gate | Additional errors relative to the typed gate |
| --- | ---: |
| Full typed gate | 0, admitting 54 and refusing 4,146 |
| Capability overlap | 18 false admissions |
| Capability equality | 36 false refusals |
| Numeric threshold with receipt scope, metric and artifact ignored | 18 false admissions |

With an exact platform and authority, a representative candidate passes a required maximum of 20 for bounds of 19 or 20. It is refused for 21, missing evidence, a stale artifact, a different workload configuration, or a sample median presented as an upper bound. All those numeric records are optional in the no-mandatory-bound profile and have no effect on eligibility. None of the numbers are load measurements. General evidence trust, dynamic grant changes, conformance of adapters, actual cost estimation and authorized production profiles remain open. [Ledger](SELECTION-CONSTRAINTS-01/evidence.json)

## Reproduction

Use Lean 4.36.0 at revision `611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9` and CPython 3.12.14.

```sh
study=research/compiler-and-translation/RT-13/SELECTION-CONSTRAINTS-01
build=$(mktemp -d)
for seed in 37 75; do
  LC_ALL=C PYTHONHASHSEED="$seed" python "$study/run.py" --lean /path/to/lean \
    --output "$build/result-$seed.json"
done
cmp "$build/result-37.json" "$build/result-75.json"
cmp "$build/result-37.json" "$study/evidence.json"
```

[Runner](SELECTION-CONSTRAINTS-01/run.py)
