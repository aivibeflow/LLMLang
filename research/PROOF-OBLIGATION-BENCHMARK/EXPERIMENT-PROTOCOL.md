# Experimental protocol

## Stages and controls

A: natural-language intent to authoritative contract (use the independent [CF corpus](../CONTRACT-FORMALIZATION-CORPUS/README.md)). B: accepted contract to obligation graph. C1: classify and plan; C2: translate and establish correspondence; C3: verify; C4: aggregate and invalidate evidence. Run B with gold contracts; run C with reviewed gold obligations; also run end-to-end without rescuing earlier errors. Public seed cases are development-only. Freeze a held-out revision set with family-level separation, paraphrase variants, and independent reviewers; prevent exposure to gold labels, obligation IDs, oracle source, mutation tags and expected verdicts. Public repository cases cannot establish absence from training data. Use the blind export only for B, not as a full C prompt.

## Required run provenance

Persist immutable run ID, case ID/revision/content hash, source/contract and implementation snapshot, split, prompt and raw response, model exact version and settings, seed where available, repetition, normalization and evaluator versions, planner/backend/profile/translator/checker versions and configuration, proof artifacts and counterexamples, assumptions, bounds, dependency closure, correspondence and TCB, outcome and uncertainty, time/token/cost/resource budget. Store raw logs without secrets; hashes bind exact artifacts. Never overwrite a completed run; publish failed runs as well. Missing, malformed, timeout, unsupported and abstention remain observable. The [run record schema](run-record.schema.json) is an experimental interchange starting point.

## Metrics

Report denominators and counts by family, stage and model; no single composite score.

- B obligation precision = semantically valid matched generated claims / all generated claims; recall = covered required gold claims / required gold claims; report missing, duplicate, strengthened, weakened, contradictory and vacuous claims. Independent reviewers match by semantic entailment, not identifier or wording; allow equivalent decompositions and adjudicate disagreements.
- Multi-label taxonomy: per-label precision/recall, micro/macro F1 and exact set match, with undefined denominator reported as unavailable.
- C1: eligible selections / attempted selections; recall of required capabilities and correct abstentions / expected abstentions; report unsafe selection separately.
- C2: checked correspondence / attempted translations, with weakened and unsupported translations tracked separately.
- C3/C4: exact verdict accuracy = correct / all expected records; report invalid and missing records; false-proven on negative controls = incorrect proven / all disproven gold cases. Also report unsound proof promotion among all cases whose gold status does not warrant proven. Distinguish incomplete proof coverage, conditional results and bounded checks. Do not treat unsupported or unknown as disproven.
- Reproducibility: independently replayable runs / runs; report cost and latency distribution and raw counts. Use paired same-case comparisons and case-family clustered confidence intervals; repeat stochastic runs with frozen budget. Pre-register sample sizes and stopping rules before held-out evaluation.

The current runner implements only exact verdict scoring on finite smoke records (not semantic matching). Prediction JSON is a list of objects with case_id, revision, case_sha256, variant and status. Unknown, duplicate or stale identifiers fail; omitted predictions count as wrong. Run `python research/PROOF-OBLIGATION-BENCHMARK/run.py score --predictions predictions.json`. This score is diagnostic, not an LLM benchmark without blinded inputs and independent adjudication.

## Falsifiers and expansion gates

Require controls for unsatisfiable preconditions and vacuous truth, undefinedness, dependent typing, incompatible caller/callee assumptions, silent contract strengthening, unsupported features, stale snapshots, malformed or forged evidence, translation that drops constraints, solver disagreement, bounded-only success, conditional assumptions, and missing obligations. Extend to real linearizability, weak memory, unbounded fairness, distributed faults, numerical error/NaNs, randomized guarantees, security hyperproperties, migration and version compatibility. The initial taxonomy is not complete; annotate cross-cutting semantic features rather than force new labels. Use existing research scenarios with exact revision and independent semantic oracle.

Compare Lean, SMT and TLA+ on shared eligible claims, not a fixed backend-per-label mapping. Pin versions and configurations, distinguish solver trust from checked certificates, and replay counterexamples. Evidence flags in the seed aggregation policy are test fixtures, not proof of their own truth. Only a validated evidence graph may supply them in a real pipeline. See #395 and #397.

The [second cohort coverage and review record](COVERAGE-AND-REVIEW.md) defines concrete witnesses and the independent adjudication gate. All public cases remain development data.
