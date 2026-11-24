# Exact verification receipts after a typed-SPG provider rebind

- **Date:** 2026-11-24
- **Research:** RT-05, RT-20, RT-32/33
- **Baseline:** `b7a4c0d3ed80eb4dae5c54af1943e00d0d6e78d5` (main after PR #465)
- **Evidence:** Reproduced finite observations and Lean verdicts composed by the existing receipt evaluator

The semantic identity of the caller and its public claim stayed constant across a compatible provider rebind. The exact caller receipt's premise closure and verification key changed. Submitting the old caller receipt alongside fresh provider evidence therefore left the aggregate insufficient. An exact recheck of both obligations restored bounded agreement.

## Comparison

The [typed-SPG pilot](PUBLIC-INTERFACE-SPG-OBSERVATION-PILOT-2026-11-24.md) covers two fixture source surfaces, three scalar inputs, ordered effects, and exact binding. This replay regenerates its full observation and Lean verdict ledger, compares it with the archived artifact, then selects three cases. The original provider adds one and the replacement adds two. The public contract allows both offsets and fixes the trace order. The third case binds the replacement while claiming the original provider's offset.

Each plan contains a caller claim over the same public contract and observation projection, and a prerequisite claim that checks the selected provider body and its refinement. A direct public-body verdict supplies the caller support in this pilot. The separate body and refinement verdict supplies support or a counterexample for the provider. The script passes the resulting exact receipt keys to the [evidence composer](../../formal-verification/PROOF-OBLIGATION-BENCHMARK/EVIDENCE-COMPOSITION.md) through a fixture-local allowlist. It also computes the [prototype verification key](../../research-management/RT-00/RT-00-C-VERIFICATION-REUSE-IDENTITY-RECHECK-2026-11-24.md) using the caller subject, transitive premise closure, checker, projection and exact binding assumption.

```mermaid
flowchart LR
  C[Stable caller and public claim] --> E[Exact verification receipt]
  P[Selected provider and its contract] --> D[Provider premise closure]
  D --> E
  E --> K[Applicable to the checked binding]
```

| Submission | Caller status | Provider status | Aggregate |
| --- | --- | --- | --- |
| Original binding and both checked receipts | Bounded agreement | Bounded agreement | Bounded agreement |
| Replacement with both original receipts | Insufficient, stale premises | Insufficient, different claim | Insufficient |
| Replacement with original caller and fresh provider receipts | Insufficient, stale premises | Bounded agreement | Insufficient |
| Replacement with fresh caller receipt and no provider receipt | Conditional | Insufficient | Insufficient |
| Replacement with both receipts checked again | Bounded agreement | Bounded agreement | Bounded agreement |
| Replacement claiming the original provider's offset | Conditional | Refuted | Refuted |

Subject-only reuse would treat the original and replacement as the same checked caller execution and would miss a change observed in the provider premise. Exact closed-execution reuse distinguishes them. A reusable modular caller proof parameterized by any provider satisfying the public contract remains a separate candidate. It requires a checked caller theorem under the abstract contract, an admissible provider witness and a checked composition rule. This pilot evaluates concrete finite receipts and their applicability. Its allowlist represents fixture-local authorization after replay. Production authorization, exact dependency coverage, general source correspondence, and ownership, progress and foreign contracts remain open.

## Reproduce

The run used Python 3.12.14 and Lean 4.36.0 (`611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9`). The archived [result ledger](public-refinement-pilot/rebind-results.json) records exact SHA-256 values for the source files used directly and for the observation ledger, plus both provider bindings, both verification keys and the rejection reasons by receipt key. From the repository root with the pinned tools on the path:

```sh
pilot=research/semantic-representation/RT-05/public-refinement-pilot
replay_dir=$(mktemp -d)
python3 -B "$pilot/provider_evidence_rebind.py" --output "$replay_dir/rebind-results.json"
cmp "$pilot/rebind-results.json" "$replay_dir/rebind-results.json"
```
