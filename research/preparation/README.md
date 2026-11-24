# LLMLang Research Preparation Pack

**Status** — Prepared for execution. Individual briefs track bounded results as they become available.

**Baseline:** `main` at `cf96386b40604f870f864e8d6bc93dac4d12bbcd` (2026-11-20).  
**Purpose:** Convert the current plan, open-question register, and existing evidence into executable research briefs.  
**Normative boundary:** These briefs are research instructions only. They select no language profile, hash schema, runtime, backend, package format, or security policy.

## External source material

The [External Research References and Snapshots](../references/README.md) register maps the briefs to official source documents. It includes versioned local copies of licensed MCP, OCI, Alive2 and Bazel REAPI materials, plus canonical links for SMT-LIB, cvc5, Lean, LLVM, language memory models, SQLite, Git, Nix and POSIX. Use its version/attribution notes before execution.

## How to use this pack

Start with this index, then read the linked baseline documents and the relevant brief as one unit. A brief is ready to execute when its dependencies and input fixtures are available. During execution, update the result document and the central state/index; do not turn a proposed test matrix into an observed result.

Every study must record:
- exact source commit, branch, toolchain and dependency versions;
- the input fixtures and their provenance;
- commands, configuration, seeds, limits, raw outputs and reproduction steps;
- positive, negative, rejected and UNKNOWN cases;
- which claims are observations, tests, proofs, assumptions or conjectures;
- limitations, falsifiers, cross-area implications and affected open-question IDs.

Do not infer completeness from a bounded prototype, passing tests, a second implementation, or a matching generated output. State the exact fragment and assumptions each result covers.

## Execution order

| Order | Preparation brief | Main questions / gates | Dependencies |
|---:|---|---|---|
| 1 | [RT-03/04 source semantics, calls, effects and ownership](RT-03-04-SOURCE-SEMANTICS-AND-OWNERSHIP.md) | Gate A; COR-13 source/snapshot correspondence; ordered effects; transfer/cleanup; recursion and budget | Current COR-13 corpus, RT-03/04 shared fixtures |
| 2 | [RT-04 provider reconciliation and guard coverage](RT-04-PROVIDER-RECONCILIATION-AND-GUARD-COVERAGE.md) | Independent providers, concurrent result delivery, restored snapshots, alias escape and reentry | Scenarios 124–132; invocation journal model |
| 3 | [RT-03/06/07 path feasibility and source correspondence](RT-03-06-07-PATH-FEASIBILITY-AND-SOURCE-CORRESPONDENCE.md) | Solver trust/UNKNOWN, mutable predicate identity, source-to-CFG and proof boundary | Scenarios 102–108; Scenario 34 / SCW work |
| 4 | [RT-05/06 identity and dependency completeness](RT-05-06-IDENTITY-AND-DEPENDENCY-COMPLETENESS.md) | Stable identity, typed hash domains, SCCs, graph dependencies, import and negative lookup evidence | Draft Glossary, RT-05, RT-20, RT-24 |
| 5 | [RT-07/09/10/13 evidence and backend preservation](RT-07-09-10-13-EVIDENCE-AND-BACKEND-PRESERVATION.md) | Evidence reuse/trust, source-to-IR, LLVM and second-backend vertical slice | Gate A semantic subset; Scenarios 34, 96, 133 |
| 6 | [RT-11/12 package and cache validation](RT-11-12-PACKAGE-CACHE-AND-TRUST.md) | Immutable-store adapter, dependency closure, large indexes, action/result trust | LL-021/022; package and cache prototypes |
| 7 | [RT-16/19/20/22/23 Toolchain security and lifecycle](RT-16-19-20-22-23-TOOLCHAIN-SECURITY-AND-LIFECYCLE.md) | Persistent multi-client authorization, crash recovery, worktree isolation, exact-tree commit | RT-19–23 contracts and implementation prototypes |
| 8 | [RT-01/14/17 workload and agent evaluation](RT-01-14-17-WORKLOAD-AND-AGENT-EVALUATION.md) | Workload weights, authoring success, repair, diagnostics, context and scope safety | Reference workload catalogue; stable candidate slice |

## Cross-document reading rules

- **RT-03 and RT-04 are a coupled study.** Read the shared semantics corpus, COR-13 follow-up, RT-04 alternatives and the scenario evidence together. Do not treat a resource outcome as a type rule until the source-level observation and call-boundary model are explicit.
- **Identity-bearing work must read the [Draft Glossary](../../draft/GLOSSARY.md).** Preserve the separate meanings of generic `ContractHash`, `OpHash`, `ImplHash`, `CCHash`, optional `CandidateSetHash`, and evidence identity. The glossary remains a proposal, not an accepted canonical encoding.
- **RT-20 / RT-24 / RT-23 are one lifecycle cluster.** Change planning, semantic merge, mapping revisions, repository/worktree state and commit recovery must be reconciled before end-to-end claims.
- **Formal proof, solver output and test evidence are different evidence classes.** A proof for a restricted fragment does not certify unsupported source constructs.

## Source correspondence milestone

Scenario 34 records scope validation, typed environments, and expression-level correspondence in SCW-06–09. Use its task ledger for the command and program proof layers. [Scenario 34](../formal-verification/RT-07/RESEARCH-SCENARIO-34-SOURCE-TO-QUERY-SEMANTIC-CORRESPONDENCE.md#72-source-syntax-typing-and-environments)

## Completion condition for this preparation pack

This pack is complete when each planned study has a scoped question, linked prior evidence, required inputs, a discriminating test matrix, explicit UNKNOWN/failure behavior, acceptance gates, deliverables and a named downstream decision boundary. Completion of the pack is not completion of any research question.
