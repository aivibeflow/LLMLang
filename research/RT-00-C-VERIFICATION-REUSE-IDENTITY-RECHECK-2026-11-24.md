# RT-00 C — Verification reuse identity recheck

**Date:** 2026-11-24
**Current-main baseline:** `ebaaefe7ceb80fb187d96d54e8428efdfb65b872`
**Plan mapping:** §0.1 prototype claim/reproducibility audit; §3.2 incremental analysis and invalidation; Scenario 04 verification reuse
**Status:** bounded source-and-test recheck; no verification-cache policy selected

## Question

Scenario 04 proposes safe reuse of test, analysis, and proof results. Which parts of the prototype's verification identity are actually enforced by current code, and should assurance-policy changes invalidate execution results in the same way as changes to the subject, verifier, or environment?

This study checks a specific implementation boundary on current `main`; it does not validate a production cache or the correctness of any cached proof.

## Current-main code and test evidence

`research/PROTOTYPES/DEPENDENCY-GRAPH-01/src/semantic_graph.py::verification_key` hashes:

- semantic subject/value hash;
- dependency-closure digest;
- verifier identity;
- verifier configuration;
- sorted assumptions.

It does not accept separate environment/toolchain or assurance-policy identities. Related binding tests additionally include the selected binding in an executable-verification key. This supports separation between semantic subject identity and the identity of a verification action, but does not demonstrate complete production input capture.

Ran these focused current-main suites with CPython 3.12.14 from `research/PROTOTYPES/DEPENDENCY-GRAPH-01`:

```sh
python3 -B -m unittest discover -s tests -p 'test_semantic_graph.py' -v
python3 -B -m unittest discover -s tests -p 'test_binding.py' -v
python3 -B -m unittest discover -s tests -p 'test_requirement_evolution.py' -v
```

**Result: 26/26 tests passed.** The suites check that semantic dependency changes propagate to dependent hashes, unrelated provenance does not alter semantic hashes or the tested verification key, binding changes alter executable verification identity, and changes to semantic requirements invalidate the tested verification identity. They do not exercise a persistent result store, machine-checked proof-certificate reuse, or policy migration.

An additional direct sensitivity probe of the current `verification_key` produced a different key after each of five single-field changes: subject, dependency closure, verifier identity, configuration, and assumptions. This confirms the tested function's declared sensitivity only. The explicit API has no standalone environment/toolchain or acceptance-policy parameter; a caller could pack those into config, but that representation is not enforced by this function.

Exact source SHA-256 at the baseline:

| File | SHA-256 |
|---|---|
| `src/semantic_graph.py` | `7bd76ce205ae9b569421856bb5379141103f0aa31d203cf41deecdac4fadf0ea` |
| `tests/test_semantic_graph.py` | `60e65ad28b465c3ab38909f025328b31c0d243b2dc3ba8b36f1af99aa31cbca0` |
| `tests/test_binding.py` | `9016e17a51892903df21c0a5dd8f2bc0c1fefabfc8c17e009c2b91e2040b752d` |
| `tests/test_requirement_evolution.py` | `6d292c852b47dc122108eabbcd76801947e4aa52500e875c27962ae150b48427` |

## Candidate designs

| Design | Identity and reuse rule | Advantage | Risk / missing validation |
|---|---|---|---|
| **A — One exact result key** | Hash subject, proposition/tests, complete dependency closure, verifier/toolchain, configuration, assumptions/environment, and acceptance policy into one key. | Simple conservative gate; mismatches are misses. | Policy-only changes rerun the verifier even when a stored proof object can be checked against the new policy. Omitting a field remains unsafe. |
| **B — Execution identity plus applicability evaluation** | Key the execution/result by the exact subject, obligations, dependency closure, verifier, relevant toolchain/config, and assumptions. Store the result/certificate separately. At use time, evaluate its scope, trust, and assurance level against the current policy. | Separates “what ran and on what” from “whether this evidence currently satisfies the gate”; can reuse an archived proof certificate if a trusted checker establishes applicability. | Requires a sound result schema and checker. Test outcomes generally cannot migrate across runtime/environment changes without explicit equivalence evidence. Policy weakening or strengthening must be explicit and auditable. |
| **C — Subject-only cache** | Reuse by semantic subject hash or stable ID; attach verifier and policy as informal metadata. | Highest apparent hit rate and smallest key. | Unsound: different verifier/config/assumptions can change the result while the subject is unchanged. Direct prototype sensitivity tests falsify this shortcut for the tested identity model. |

### Evidence-specific consequences

- A test result is an observation of an executable under a runtime, fixture set, environment, and harness. A relevant change to any of these normally requires a new execution; retaining the old log is useful for history but does not make it current evidence.
- A machine-checked proof artifact may be retained across a policy change if a trusted checker can establish that the exact proposition and assumptions meet the new gate. This is a separate check, not automatic reuse of the old “passed” status.
- A verifier or kernel change conservatively changes the execution identity. A proof certificate may then be rechecked by the new trusted kernel without regenerating the proof, if the certificate format and semantics are compatible. That compatibility path has not been implemented or measured here.
- Unknown dependency or environment closure prevents an applicability result from being treated as safely reusable; preserve the result as historical evidence and fail closed for the current gate.

## Result and implementation comparison

The current code supports the first part of **B**: identity is distinct from semantic content and the tested fields alter the key. It does not implement the applicability layer needed for proof-certificate reuse or explicitly bind environment/policy. **A** is the lowest-risk initial rule for a production execution cache: include every result-determining input and miss on any relevant mismatch. **B** is the better long-term model for keeping artifact identity separate from current assurance decisions, especially for machine-checkable certificates, but requires a trusted recheck path.

Therefore, the candidate implementation boundary is:

1. Keep an exact `VerificationExecutionKey` for each execution/proof-generation action, covering the complete subject, dependency closure, verifier/toolchain, configuration, assumptions, and captured environment.
2. Store the immutable output/certificate and an evidence record separately from its key.
3. Compute current applicability against the requested policy and current trust/revocation state. Do not mutate an old result from `STALE`/`UNKNOWN` to current merely because its subject hash matches.
4. Permit certificate rechecking as a distinct action with its own key; do not generalize that reuse rule to test executions.

This is a recommendation for the next cache-contract experiment, not an accepted design. It depends on complete input discovery, authenticated evidence provenance, a versioned proof-certificate format, and trust policy.

## Limits and external dependencies

- The 26 tests use an in-memory synthetic model; no production test/proof cache or compiler is exercised.
- No verifier environment or assurance-policy field is currently required by the `verification_key` API. Config may carry some of this information, but the model does not enforce a canonical field contract.
- The direct key-sensitivity probe did not validate a real result cache hit/miss decision or trust boundary.
- Certificate rechecking across kernel versions, revocation, signatures, remote provenance, and concurrent policy updates remain untested.
- The semantic dependency closure may be incomplete for dynamic, generated, environmental, or external inputs; the result cannot support safe reuse unless that completeness is established.

**Conclusion:** subject identity alone is insufficient; the current prototype demonstrates this for five declared key dimensions. Use exact execution identity for conservative result reuse and a separate applicability/recheck step for policy and certificate reuse. Production identity, completeness, trust, and lifecycle rules remain open in §3.2 and RT-16.
