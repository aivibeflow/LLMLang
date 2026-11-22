# Change Set Verification and Acceptance Gate

**Status:** User-confirmed discussion synthesis; candidate Toolchain behavior, not yet a normative API contract  
**Date:** 2026-11-22  
**Primary research area:** RT-19 — Toolchain Server and Semantic Development API  
**Related areas:** RT-05 (typed SPG), RT-06 (semantic dependencies and impact), RT-07/08 (formal verification and evidence), RT-20 (change planning and hash propagation), RT-24 (semantic merge)

> This document records the Change Set verification and acceptance behavior confirmed in the LLMLang architecture discussion. It refines the candidate lifecycle in RT-19 and the concurrency/acceptance model in Scenario 02. It does not define final MCP schemas, verifier internals, or a normative language rule.

## 1. Scope and design principles

AI agents work against the canonical Semantic Program Graph (SPG) through high-level semantic operations. They do not directly mutate graph storage or edit source files as their normal development interface.

A Change Set is an isolated proposal. Its working SPG may evolve through a sequence of semantic changes, but it cannot become an accepted snapshot unless the required checks succeed for the exact candidate state being accepted.

The verification model separates:
- mandatory validation of each resulting SPG state;
- mandatory contract checking and formal verification at the acceptance boundary;
- optional background contract checking and formal verification after each SPG change.

A background failure is actionable feedback for the responsible agent and a hard acceptance blocker. It is not merely advisory.

## 2. Validation after every SPG change

Every semantic operation that changes the SPG must be followed by mandatory SPG validation before the resulting state is made the current working state of the Change Set.

The immediate validation covers, at minimum:
- graph structural integrity;
- validity and resolution of semantic relationships;
- type correctness;
- LLMLang structural and semantic constraints that are part of SPG validity.

If this validation fails, the mutation is rejected atomically: the Change Set remains at its previous valid working SPG state. A failed mutation must not leave a partially updated graph.

This per-change SPG validation is mandatory and is distinct from contract checking and formal verification.

## 3. Contract checking and formal verification

### 3.1 Mandatory acceptance checks

Before a Change Set can be accepted, Toolchain must run or establish current successful evidence for both:
1. contract checking over the candidate state and its affected semantic scope;
2. formal verification required by the applicable verification policy.

Acceptance is permitted only when both checks have successful results applicable to the exact candidate SPG revision and its relevant verification inputs.

A verifier result of failure, unknown, incomplete coverage, timeout, cancellation, or unavailable verifier is not success. Such a result cannot satisfy the acceptance precondition.

### 3.2 Optional background checks

Toolchain may optionally start contract checking and formal verification in the background after each SPG change. This is an early-feedback mechanism; it does not replace the mandatory acceptance checks.

Background results are bound to exact inputs, including at least:
- Change Set identity and revision;
- candidate SPG root/revision;
- relevant contract and dependency inputs;
- verifier/tool identity and configuration required to interpret the result.

Evidence from an earlier revision must not be treated as current for a later revision unless a sound evidence-reuse rule establishes that it remains applicable. Otherwise the affected checks must be rerun.

## 4. Background failure notification and acceptance blocking

When a background contract check or formal verification detects an error or returns a non-success result that violates an acceptance obligation, Toolchain must:

1. publish a structured diagnostic/event to the responsible agent;
2. identify the Change Set and exact candidate revision/SPG root checked;
3. identify the failed contract or verification obligation, affected semantic entities, and relevant evidence/diagnostic handles;
4. provide actionable information sufficient for the agent to investigate and correct the issue;
5. mark the current candidate as blocked for acceptance.

The agent may continue working on the Change Set to correct the problem. The discovered problem must not be silently discarded or hidden by subsequent operations.

A later SPG change creates a new candidate revision. Prior diagnostics and verification evidence remain associated with the revision that produced them. Acceptance of the newer revision requires successful, current evidence; a previous failure is cleared only when the applicable obligation has been successfully rechecked for the candidate being accepted.

The notification is not an authorization decision and does not itself modify or accept the SPG.

## 5. Explicit acceptance attempts use the same gate

The acceptance operation must enforce the same verification policy regardless of how acceptance is requested.

When an agent explicitly invokes the accept operation:
- Toolchain checks the current candidate revision and its evidence;
- if a relevant background failure remains applicable, acceptance is rejected and the agent receives the corresponding diagnostics;
- if required checks have not run or their evidence is stale, Toolchain runs or schedules the mandatory checks and does not accept while they are unresolved;
- if any required check fails, returns unknown/incomplete, or cannot complete, acceptance is rejected;
- only successful current contract-checking and formal-verification evidence can satisfy the gate.

The acceptance endpoint must enforce this rule itself. It must not trust an agent-supplied claim, a client-side status, a previous success for another revision, or the mere fact that an acceptance request was made.

A blocked acceptance attempt leaves the accepted snapshot/head unchanged and does not partially publish the candidate.

## 6. Verification state and evidence

The Toolchain should expose verification status as distinct dimensions rather than one ambiguous `valid` flag.

At minimum, report:
- **SPG validation:** valid or invalid for the current working revision;
- **contract checking:** not run, pending, passed, failed, unknown, or stale;
- **formal verification:** not run, pending, passed, failed, unknown, or stale;
- **acceptance eligibility:** eligible or blocked, with explicit blocking reasons.

Each result must be associated with exact input identities and a verifier identity/configuration. The agent-facing diagnostic/event should include stable codes, severity, affected Stable IDs, checked revision/root, and references to detailed evidence.

A successful SPG validation does not imply successful contracts or formal verification. A successful background run for one revision does not imply success for another.

## 7. Merges and combined candidates

Merging independent Change Sets creates a new candidate state. Successful checks on the individual Change Sets do not establish correctness of their combination.

The merged candidate must:
1. pass mandatory SPG validation after each applied semantic change, or an equivalent atomic validation boundary for the merge transaction;
2. undergo contract checking and formal verification before acceptance;
3. be blocked from acceptance if a required check fails or remains unresolved.

Evidence may be reused only when the Toolchain proves that its exact inputs and scope remain applicable to the merged candidate. If non-impact cannot be proved, the relevant checks must be performed again.

## 8. Confirmed behavior

| Area | Confirmed direction |
|---|---|
| Agent mutation interface | High-level semantic operations over SPG; no ordinary direct graph mutation |
| Per-change validation | Mandatory SPG validation after every SPG change |
| Per-change contract checking | Optional background execution |
| Per-change formal verification | Optional background execution |
| Acceptance boundary | Contract checking and formal verification are mandatory |
| Background failure | Notify the responsible agent with structured, actionable diagnostics |
| Blocking | A detected acceptance-relevant error blocks Change Set acceptance until corrected |
| Agent workflow | The agent may continue working to fix the issue; acceptance remains blocked |
| Explicit accept request | Enforces exactly the same gate; an attempt cannot bypass or override a failure |
| Evidence freshness | Results are tied to exact revisions/inputs; stale evidence is not success |
| Unknown/incomplete result | Does not satisfy a mandatory acceptance check |
| Merge | The combined candidate requires its own applicable validation and verification |
| Failure atomicity | Rejected mutation/acceptance leaves the prior working/accepted state intact |

## 9. Open implementation details

The following details remain for the Toolchain API and implementation design:
- exact SPG validation rule set and diagnostic taxonomy;
- exact contract-checking and formal-verification job interfaces;
- event delivery, acknowledgement, retry, and reconnect semantics for agent notifications;
- whether background jobs are coalesced or cancelled when a newer revision supersedes their inputs;
- precise evidence-reuse rules and dependency-closure representation;
- verifier scheduling, resource limits, and cancellation behavior;
- exact transaction boundary and persistence model for atomic acceptance.

These details must preserve the confirmed behavior above. In particular, implementation convenience must not weaken the acceptance gate or allow an explicit acceptance request to bypass it.
