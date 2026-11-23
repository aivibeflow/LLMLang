# RT-00 — Pinned Lean proof source and checker verification for Stage 0.2

**Research item:** [issue #285](https://github.com/aivibeflow/LLMLang/issues/285), [PLAN §0.2](../PLAN.md#02-establish-research-quality-and-decision-rules)  
**Date:** 2026-11-23  
**Status:** Fresh, source-pinned Lean 4.36.0 proof check proposed; CI outcome not yet observed  
**Provenance baseline:** `ff1295c1769bfe8546c4b63590c9f607349215ee`  
**Evidence class:** Independent *toolchain execution* of archived Lean proofs; not an independent mathematical peer review or full-language semantics guarantee  
**Source:** `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/ObservableRewrite.lean`  
**Git blob:** `98bd38f297e91840c56664ef00fbd5f28c3a81b8`; **SHA-256:** `039808b6adf5d5baa97f6498a15fd04843a4f4c6b1147c9dade68f4440252765`  
**Lean toolchain:** `leanprover/lean4:v4.36.0`; **toolchain config Git blob:** `00f848359b1cdaf7c12cd6b7acc5b4364752e154`  
**Draft impact:** **None.** A bounded proof is not an accepted optimizer guarantee.

## Research question and alternatives

[RT-07](RT-07-OBSERVABLE-REWRITE-CORRECTNESS.md) and the [DEP-007 evidence recheck](RT-00-DEP-007-OBSERVATION-MODEL-RECHECK-2026-11-23.md) report a Lean-checked theorem that selected expression rewrites preserve the model's outcome and ordered event trace. The [Stage 0.2 claim register](quality-audit/2026-11-23-claim-cohort2.json) identifies the assertion as a **Proof** *within the declared grammar*, not as an end-to-end LLMLang optimizer proof.

Can a fresh runner **independently execute** Lean 4.36.0 on that **exact archived file**, verify that it typechecks with warnings-as-errors, and preserve the kernel's printed axioms, without silently switching to today's source or claiming to verify the missing source/IR/backend bridge?

- **H1 (testable):** the exact Git object and SHA-256 agree with the versioned report; a fresh pinned Lean 4.36.0 checks the six declared theorems in the standalone source file.
- **H2 (unsupported by this check):** the theorem automatically proves preservation for all LLMLang source expressions, lowering and native target behavior. No source-to-typed-grammar correspondence or target compiler simulation relation is supplied.
- **Alternative rejected:** rely only on a prior report's `lean` success or recent Required CI running the current repository revision. Those are useful prior evidence, but cannot by themselves identify a fresh run of the exact audited file at the exact historical source baseline.

**Prior art:** [RT-07](RT-07-OBSERVABLE-REWRITE-CORRECTNESS.md), [DEP-007 proof identity review](RT-00-DEP-007-OBSERVATION-MODEL-RECHECK-2026-11-23.md), [source and query semantics boundary](RESEARCH-SCENARIO-34-SOURCE-TO-QUERY-SEMANTIC-CORRESPONDENCE.md), [observable rewrite source](PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/ObservableRewrite.lean), and [the Required CI Lean job](../.github/workflows/logos-binding.yml).

## Reproduction method, fixtures, and expected output

The new [archival proof workflow](../.github/workflows/research-quality-pinned-lean-proof.yml) checks out exact commit `ff1295c`, verifies source/tree blob and SHA-256, asserts the `lean-toolchain` config, installs Lean `4.36.0` and runs:

```sh
cd research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding
lean --version
lean -DwarningAsError=true ObservableRewrite.lean
```

**Expected:** exit code **0**, no error/warning from Lean; the source's `#print axioms` outputs identify its actual trusted assumptions for the main theorem and counterexample theorems. Exact Git revision/source/toolchain hashes and Lean stdout/stderr are preserved as CI artifacts. The standalone module imports `Std` and does not require an external solver or a linked real LLMLang compiler. The toolchain installer in CI uses the same official elan-install route as the existing Required CI, which is a networked installation trust input, not a cryptographic attestation of the entire host.

The source explicitly declares `foldAdd_preserves`, `foldChoose_preserves`, `rewrite_preserves`, `swapping_addends_changes_trace`, `discarding_equal_branch_guard_hides_failure`, and `keeping_trace_before_failure`. The last three are finite-grammar counterexample/failure witnesses. The proof-level expected observations are equality of `Except Nat` outcome and ordered `List Nat` event trace under the selected rewrites, with concrete negative cases for swapping emitting operands or erasing a failing guard.

**Observed run:** **pending**. Neither this new workflow nor the report alone can assert a passing Lean run before successful CI.

## Scope, falsifiers and evidence interpretation

- The mathematical integer semantics has **no machine integer overflow**; event lists omit state, aliasing, cleanup, foreign calls, concurrency and resource consumption. Failure is modeled as an `Except Nat` and the selected expression grammar is not the complete source/SPG language.
- A checked `rewrite_preserves` theorem would validate the rewrite *inside the Lean model*, not the interpretation of real source into that model or its preservation through a compiler backend.
- The earlier [RT-07](RT-07-OBSERVABLE-REWRITE-CORRECTNESS.md) already states that `Classical.choice`, `propext` and `Quot.sound` are standard Lean assumptions. This recheck must quote the **actual printed axioms**; do not infer `no axioms` from absence of `sorry`.
- The associated source correspondence and parser/CFG/optimizer integration obligations remain open. This check will not settle ADRs, approve a `draft/` optimization rule or justify closing issue #285.

**Review recommendation only:** require a separate source/semantic observation mapping and checker-authority review for any downstream optimizer acceptance; treat the archival Lean result as bounded proof evidence. The original eight experiment worktree/host attestations, independent human scientific review, corpus-level claim validation and Stage 0.2 maintainer adoption are unrelated outstanding gates.
