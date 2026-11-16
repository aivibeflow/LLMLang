# RFC: Request and Change Model for LLMLang

**Status:** Proposed  
**Version:** 0.1  
**Target:** LLMLang  
**Document:** `RFC-REQUEST-CHANGE.md`  
**Scope:** Development workflow, change proposals, human review, content addressing, and traceability  
**Normative language:** The words MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY express requirements of this RFC when written in uppercase.

> This RFC proposes a workflow and object model. It does not claim that the proposed objects, states, APIs, or policies are already implemented or accepted by the LLMLang project.

---

## 1. Summary

This RFC defines how a person expresses a development request, how LLMLang turns that request into reviewable business semantics, and how proposed changes move safely from intent to accepted program snapshots.

The central proposal is:

- A **Request** records the human's intent and the conversation and decisions used to clarify it.
- A **Change** is a reviewable proposal to alter one or more semantic objects in the Semantic Program Graph (SPG).
- A **Change Set** groups related changes into a unit that can be validated, reviewed, accepted, and committed consistently.
- The **Specification Graph** is the authoritative structured representation of confirmed requirements and business rules.
- Design and implementation changes are derived from, and traceable to, the accepted specification, while remaining independently content-addressed graph layers.
- LLMs propose and explain changes. They do not silently approve business meaning or certify their own correctness.
- Deterministic validators and verification tools independently check structural and semantic constraints.
- Human-readable business views and semantic diffs are first-class interfaces, not incidental renderings of source code.

The workflow is deliberately incremental. A small implementation-only change may not require a full specification process if it demonstrably preserves existing externally observable behavior and project policy permits it. Conversely, any change to confirmed business meaning requires explicit review according to project policy.

## 2. Relationship to Existing LLMLang Documents

This RFC was prepared against the current repository versions of `LLMLang-CONCEPT.md` and `TOKEN_EFFICIENCY.md`.

### 2.1 Existing conceptual commitments retained

The following ideas are already established in the concept document and are treated as constraints by this RFC:

1. A program is represented primarily as a typed Semantic Program Graph with stable object identifiers, content hashes, relations, dependencies, and provenance.
2. Specification, Design, and Implementation are distinct but related graph layers.
3. Specification describes what a program must do; Design describes how it is organized; Implementation describes its concrete realization.
4. The layers are independently existing and optional according to project policy and program complexity.
5. Contracts, effects, invariants, errors, tests, properties, and proofs are semantic objects rather than comments.
6. LLM-generated proposals are not trusted merely because an LLM produced them. Validation is independent and deterministic where feasible.
7. Verification results distinguish at least `PROVEN`, `DISPROVEN`, `UNKNOWN`, and `NOT_CHECKED`; unknown or unchecked is not success.
8. Dependency analysis identifies which downstream objects and verification results may be affected by a change.
9. Changes should be local where semantics permit, and verification should be incremental.
10. Formal verification establishes conformance to a formal specification, not that the specification perfectly captures human intent.

The token-efficiency document additionally establishes optimization goals: minimum sufficient context, minimum semantic change, and minimum feedback. This RFC applies those goals to Request and Change processing.

### 2.2 New proposals introduced here

The following are proposals of this RFC, not existing accepted language features:

- First-class `Request`, `Clarification`, `Decision`, `Change`, `ChangeSet`, and `Review` records.
- Explicit lifecycle state machines and transition rules for these records.
- A distinction between human intent, confirmed requirements, assumptions, and unresolved questions.
- A semantic review package with Business View, Formal View, impact analysis, and semantic diff.
- A two-phase acceptance and commit protocol.
- Conflict detection and resolution rules for concurrent Change Sets.
- Explicit approval policies and authority boundaries.
- A proposed provenance and audit model.

### 2.3 No silent override

If this RFC conflicts with an established concept-document commitment, the concept-document commitment takes precedence until the project explicitly accepts a change to it. This RFC is intended to extend the concept, not to redefine the semantics of the language, type system, effects, verification statuses, or runtime.

Implementation details such as database technology, wire protocol, canonical serialization, and exact UI are intentionally not fixed here.

## 3. Goals and Non-Goals

### 3.1 Goals

The model MUST:

- let a person create a request in natural language without knowing SPG internals;
- preserve the original request separately from its interpretation;
- prevent assumptions from silently becoming confirmed business requirements;
- make business rules understandable and reviewable without reading implementation code;
- represent proposed changes as structured, addressable, content-addressed objects;
- show what changes semantically, why it changes, and what may be affected;
- support independent review, explicit approval, rejection, revision, and cancellation;
- preserve a complete history of decisions and accepted changes;
- detect stale baselines and conflicting concurrent changes;
- connect requirements to design, implementation, tests, contracts, proofs, and verification results;
- invalidate or re-evaluate verification results when their inputs change;
- support incremental context assembly and patch-oriented LLM interaction.

### 3.2 Non-goals

This RFC does not:

- define the full syntax or semantics of LLMLang;
- define the complete SPG node schema;
- prescribe a particular database, VCS, event store, or collaboration protocol;
- require every project or task to use all three graph layers;
- require human approval for every implementation edit;
- treat an LLM explanation as evidence of correctness;
- guarantee that formalized requirements match the user's real-world intent;
- prescribe a specific UI framework or agent orchestration platform;
- define deployment, release, or production rollout workflows beyond the accepted-snapshot boundary.

## 4. Core Concepts and Boundaries

### 4.1 Request

A Request records **why a change is being considered**. It captures the human's intent, original wording, relevant context, clarifications, decisions, constraints, and acceptance expectations.

A Request is not itself a specification, implementation instruction, or authorization to mutate the accepted program.

A Request MAY result in:
- one Change Set;
- several independently reviewable Change Sets;
- no Change Set, if the request is informational, invalid, withdrawn, or already satisfied;
- a deferred proposal if required information is unavailable.

One Request MUST NOT be assumed to correspond to exactly one commit or one code change.

### 4.2 Clarification

A Clarification is a question, answer, or exchange used to resolve ambiguity in a Request.

It MUST preserve:
- the question as asked;
- the answer or explicit lack of answer;
- the author or source;
- the timestamp or logical sequence;
- the exact Request Content Hash to which it applies;
- whether the answer is confirmed, tentative, or withdrawn.

A clarification answer does not automatically become a requirement. It becomes a confirmed decision only through an explicit classification or approval step.

### 4.3 Decision

A Decision records a resolved choice that affects interpretation, scope, constraints, or approval.

A Decision MUST identify:
- the question or alternatives it resolves;
- the selected option or explicit decision;
- the decision-maker or authority;
- rationale, if supplied;
- affected Request and Change objects;
- whether it is binding, provisional, or superseded.

Decisions are immutable historical records. A later correction creates a superseding Decision rather than rewriting history.

### 4.4 Change

A Change is a **proposed semantic mutation** against a known graph baseline.

A Change describes:
- the target object or objects;
- the intended operation;
- the expected semantic effect;
- its source Request and relevant Decisions;
- preconditions and assumptions;
- affected dependencies;
- validation and review state.

A Change is not synonymous with a text diff. A text diff is one possible representation of a graph mutation. A Change MUST be understandable at the semantic level even when its textual rendering differs.

A Change MAY add, modify, deprecate, supersede, or remove an SPG object, subject to graph invariants and deletion policy.

### 4.5 Change Set

A Change Set groups one or more Changes that are intended to be reviewed and accepted together.

A Change Set defines:
- a common baseline;
- its member Changes;
- dependency and ordering constraints;
- validation results;
- approval requirements;
- conflict state;
- commit outcome.

A Change Set is the default unit of review and atomic acceptance. A project MAY support explicitly declared multi-Change-Set workflows, but partial acceptance MUST never happen implicitly.

### 4.6 Accepted Snapshot

An Accepted Snapshot is a consistent immutable snapshot of the applicable SPG layers after an accepted Change Set has been committed. It is addressed by a root Content Hash or an explicit tuple of layer-root hashes.

The Specification, Design, and Implementation layers may have independent root hashes, and an accepted project snapshot MUST record the exact compatible tuple of layer-root hashes from which it was produced.

### 4.7 Separation of responsibilities

| Object | Primary question | Must not be confused with |
|---|---|---|
| Request | Why does the person want something? | Confirmed specification |
| Clarification | What information resolves ambiguity? | Approval by itself |
| Decision | Which interpretation was selected, and by whom? | LLM inference |
| Change | What semantic mutation is proposed? | Accepted mutation |
| Change Set | Which mutations are reviewed and committed together? | Arbitrary file diff |
| Accepted Snapshot | What exact state is authoritative? | A working proposal |

## 5. Information Classes: Intent, Facts, Assumptions, and Unknowns

The system MUST distinguish at least four information classes.

### 5.1 Human intent

Human intent is the original goal or problem statement, preferably preserved verbatim with source and ordering metadata.

It MAY be incomplete, informal, contradictory, or ambiguous. It MUST NOT be silently rewritten to appear more precise than the user made it.

### 5.2 Confirmed requirement

A confirmed requirement is a structured statement accepted by an authorized human or by an explicitly configured project policy.

It MUST have:
- a stable requirement ID;
- a human-readable statement;
- a defined scope or subject;
- an observable outcome or a declared reason why observability is not applicable;
- acceptance criteria or a verification strategy;
- provenance to the Request and Decision that established it.

A requirement can be confirmed while some implementation details remain open.

### 5.3 Assumption

An assumption is an interpretation introduced to make progress when the Request does not determine a single answer.

Every assumption MUST:
- be labelled as an assumption;
- state its rationale or source;
- identify affected requirements or proposed Changes;
- identify the risk if it is false;
- state whether it blocks acceptance or can be accepted provisionally;
- be visible in the human review package.

An assumption MUST NOT be promoted to a confirmed requirement solely because an LLM repeats it or generates code based on it.

### 5.4 Open question

An open question is an unresolved issue that may affect scope, behavior, safety, cost, or acceptance.

It MUST have an owner or an explicit unassigned state, an impact classification, and a resolution condition. The workflow MAY continue around a non-blocking question, but MUST NOT claim full specification readiness if a blocking question remains.

### 5.5 Information state transitions

A suggested state model is:

`unclassified → confirmed | assumption | open_question | rejected`

Reclassification MUST preserve the previous state and its provenance in history.

## 6. End-to-End Development Workflow

### 6.1 Overview

The proposed workflow is:

```text
Human intent
    |
    v
Request created
    |
    v
Clarification and analysis
    |
    +---- unresolved blocking question ----> wait for answer
    |
    v
Confirmed decisions and assumptions
    |
    v
Specification proposal
    |
    v
Business review and approval
    |
    v
Change Set prepared against baseline
    |
    +---- conflict / invalid proposal ----> revise or rebase
    |
    v
Design and implementation proposals
    |
    v
Independent validation and verification
    |
    +---- failures ----> repair proposal and re-verify
    |
    v
Final review / required acceptance
    |
    v
Atomic commit
    |
    v
New accepted snapshot
```

The workflow is iterative, not strictly linear. A failed verification may lead to a revised Implementation Change, a Design Change, or—if a requirement is found to be incomplete—a new specification proposal. A change to confirmed business meaning returns to the appropriate human approval step.

### 6.2 Request intake

A person creates a Request using natural language. The system records the original text and any explicit constraints, examples, priority, scope, and desired outcome.

The person SHOULD NOT need to fill a large mandatory form. The system asks focused clarification questions only when the answer can materially change correctness or acceptance.

The system MAY infer candidate entities and relationships from the current project graph, but MUST label inferred context and allow the person to inspect its source.

### 6.3 Clarification dialogue

The LLM analyzes the Request and identifies:
- ambiguous terms;
- missing preconditions;
- alternative interpretations;
- relevant existing rules;
- possible contradictions;
- operational failure modes;
- acceptance criteria not yet defined.

Questions SHOULD be prioritized by impact. The system SHOULD ask one high-value question at a time when answers are interdependent, rather than overwhelming the person with a questionnaire.

The system MUST not ask again for information already confirmed in the Request or accepted project context unless a conflict or staleness is detected.

### 6.4 Specification proposal

The LLM proposes new or modified Specification Graph objects. The proposal MUST keep separate:
- confirmed statements;
- assumptions;
- unresolved questions;
- suggested but unconfirmed behavior.

For each proposed requirement, the system SHOULD provide:
- plain-language rule;
- applicability and scope;
- allowed and forbidden behavior;
- state transitions or conditions, where relevant;
- examples and counterexamples;
- observable acceptance criteria;
- candidate tests or proof obligations;
- links to existing requirements that may be affected.

### 6.5 Business review

The person reviews the proposed business meaning before implementation proceeds whenever the change creates, modifies, or removes confirmed externally observable behavior.

The review interface MUST prioritize the Business View and semantic diff. Formal syntax and implementation details MAY be available as expandable views.

The reviewer can:
- approve the proposal;
- reject it;
- Request state (Stable ID + Content Hash);
- resolve or defer an assumption;
- answer an open question;
- split the proposal into separate Change Sets;
- explicitly narrow or broaden scope.

Approval applies to the exact reviewed proposal hash and baseline snapshot hash. Any semantic change after approval changes the proposal hash and invalidates that approval.

### 6.6 Design and implementation

After the required specification approval, the system may propose Design and Implementation Changes.

The implementation proposal MUST reference the Specification and Design root hashes it intends to satisfy. If a Design layer is not required by project policy, the proposal can link directly to the relevant specification objects.

Implementation changes that preserve externally observable behavior MAY use a lighter approval path if policy permits. The system MUST still run the required independent checks.

### 6.7 Verification and repair

Validators and test systems run against exact graph root hashes. The system returns structured, localized feedback rather than resending full source or full reports to the LLM.

A repair creates a new Change content hash or a new Change within the same uncommitted Change Set. It MUST preserve the history of the rejected or failed proposal.

Verification status MUST be attached to the exact inputs and tool/configuration versions used. Results MUST be marked stale if any relevant input changes.

### 6.8 Final acceptance and commit

Before commit, the system checks:
- all mandatory approvals are present and current;
- no blocking open questions remain;
- all required validations have acceptable outcomes under project policy;
- no unresolved conflicts remain;
- all references and dependencies are valid;
- the Change Set baseline is still current or has been safely rebased;
- required tests and evidence are linked;
- the proposed accepted snapshot is internally consistent.

A commit creates a new immutable accepted snapshot. It does not erase the Request, proposal history, rejected alternatives, or prior accepted snapshots.

## 7. Human-Readable Business Logic

### 7.1 Business View is a first-class view

The system MUST provide a view of business behavior that a domain expert can review without reading implementation code.

The Business View SHOULD include:
- a concise statement of each rule;
- the entities and states to which it applies;
- conditions and outcomes;
- forbidden operations;
- examples and counterexamples;
- state transition diagrams;
- relevant failure cases;
- links to related requirements and scenarios;
- change history and source decisions.

The Business View is generated from structured Specification Graph objects. It is not a separate, manually maintained document that can silently drift from the graph.

### 7.2 Formal View

The Formal View exposes the structured conditions behind the prose:
- preconditions;
- postconditions;
- invariants;
- state transitions;
- effects;
- errors;
- refinement constraints;
- temporal or ordering properties where supported.

The formal model MUST be linked to the corresponding business rule. If the prose and formal expression appear inconsistent, the system MUST flag the mismatch for review rather than choosing one silently.

### 7.3 Scenario View

The Scenario View presents concrete examples in a form understandable to a domain expert:

```text
Scenario: cancellation_after_shipment

Given:
    order.state = Shipped
    order.payment_state = Paid

When:
    customer requests cancellation

Then:
    cancellation is rejected
    order.state remains Shipped
    no refund is initiated
```

Scenarios are verification objects, not substitutes for a complete formal specification. One scenario MAY verify multiple requirements.

### 7.4 Source of truth

The structured Specification Graph is authoritative for confirmed formalized business logic. Business View, Formal View, and Scenario View are projections of that graph and its linked verification objects.

Natural-language Request history remains authoritative evidence of what was asked and decided, but it is not itself the executable specification.

## 8. Proposed Object Model

The following schemas are illustrative. They do not define final serialization syntax or mandate JSON.

### 8.1 Common object metadata

Every persistent workflow object SHOULD expose a common metadata envelope:

```text
ObjectMetadata:
    id: StableId
    kind: ObjectKind
    content_hash: ContentHash
    created_at: LogicalTimestamp
    created_by: ActorRef
    updated_at: LogicalTimestamp
    provenance: ProvenanceRef[]
    lifecycle_state: State
```

Exact references SHOULD use a common structure:

```text
ObjectStateRef:
    id: StableId
    content_hash: ContentHash

SnapshotHash: ContentHash
```

Stable IDs identify logical objects. Content Hashes identify immutable canonical states of those objects. A content-addressed state MUST NOT be overwritten in place; a semantic edit creates a new hash while retaining the Stable ID.

### 8.2 Request

```text
Request:
    id: RequestId
    content_hash: ContentHash
    title: Text
    original_intent: SourceText
    scope: ScopeRef[]
    constraints: ConstraintRef[]
    priority: Priority?
    acceptance_expectations: Text[]
    clarifications: ClarificationRef[]
    decisions: DecisionRef[]
    assumptions: AssumptionRef[]
    open_questions: QuestionRef[]
    related_objects: SPGObjectRef[]
    created_by: ActorRef
    lifecycle_state: RequestState
```

The original intent MUST be preserved. A normalized summary MAY be added but MUST NOT replace the original wording.

### 8.3 Clarification

```text
Clarification:
    id: ClarificationId
    request: ObjectStateRef
    question: Text
    answer: Text?
    asked_by: ActorRef
    answered_by: ActorRef?
    sequence: Integer
    classification: confirmed | tentative | unresolved | withdrawn
    affects: ObjectRef[]
```

### 8.4 Decision

```text
Decision:
    id: DecisionId
    request: RequestRef
    question_or_issue: Text
    alternatives: Alternative[]
    selected: AlternativeRef | ExplicitDecision
    rationale: Text?
    authority: ActorRef
    status: binding | provisional | superseded
    supersedes: DecisionRef?
    affects: ObjectRef[]
```

### 8.5 Change

```text
Change:
    id: ChangeId
    content_hash: ContentHash
    request: RequestRef
    decisions: DecisionRef[]
    target_baseline: SnapshotHash
    operations: GraphOperation[]
    intent_summary: Text
    semantic_effect: Text
    assumptions: AssumptionRef[]
    dependencies: ObjectRef[]
    impact: ImpactRecord
    verification_refs: VerificationRef[]
    approval_requirements: ApprovalRequirement[]
    lifecycle_state: ChangeState
```

A Change SHOULD be small enough to explain as one coherent semantic intention. If a proposal has unrelated purposes, it SHOULD be split.

### 8.6 Change Set

```text
ChangeSet:
    id: ChangeSetId
    proposal_hash: ContentHash
    request_refs: RequestRef[]
    baseline: SnapshotHash
    members: ObjectStateRef[]
    ordering_constraints: DependencyEdge[]
    validation_summary: ValidationSummary
    review_package: ReviewPackageRef
    required_approvals: ApprovalRequirement[]
    approvals: ApprovalRef[]
    conflicts: ConflictRef[]
    lifecycle_state: ChangeSetState
    resulting_snapshot: SnapshotHash?
```

A Change Set MAY contain multiple Requests when a person or authorized workflow explicitly groups related work. This MUST be visible in the review package. The default is one primary Request per Change Set.

### 8.7 Review and approval

```text
Approval:
    id: ApprovalId
    subject: ChangeSetRef
    reviewer: ActorRef
    decision: approved | rejected | changes_requested
    scope: ApprovalScope
    baseline: SnapshotHash
    reviewed_proposal_hash: ContentHash
    comment: Text?
    timestamp: LogicalTimestamp
```

An approval is valid only for the exact proposal digest and baseline reviewed. A changed semantic proposal requires a new approval. Cosmetic re-rendering that does not alter semantic content need not invalidate approval.

### 8.8 Provenance

Provenance SHOULD support links such as:

```text
Origin:
    source_request: RequestRef
    source_decisions: DecisionRef[]
    source_change: ObjectStateRef?
    actor: ActorRef
    actor_kind: human | llm | tool | system
    model_or_tool: Identifier?
    prompt_context_digest: ContentHash?
    timestamp: LogicalTimestamp
```

Sensitive prompt contents and credentials MUST NOT be copied into provenance records. A context digest and safe references are preferable to duplicating full prompts.

## 9. Stable Identity and Content Addressing

### 9.1 Identity

IDs MUST be stable, globally unique within the relevant project namespace, and independent of display names or source-code locations.

Renaming an object MUST NOT change its ID. Moving an object between modules MUST NOT change its ID unless the move changes its semantic identity.

The exact Stable ID encoding is an open implementation decision. Human-readable prefixes such as `REQ-`, `CHG-`, and `CS-` MAY be used as display identifiers, but identity MUST NOT depend on the prefix format. Content Hashes are separate immutable state identifiers and MUST NOT replace Stable IDs.

### 9.2 Content-addressed object states

Each semantic SPG node SHOULD have its own Content Hash, including fine-grained entities such as types, operations, expressions, contracts, effects, tests, and proofs. Hashing only whole modules or packages is insufficient for precise incremental reuse and invalidation.

A node hash SHOULD be computed from a deterministic canonical encoding of:
- a domain separator and node kind;
- the node's canonical semantic content;
- its sorted, typed hash-relevant outgoing edges, each referencing the target node's exact Content Hash.

This forms a Merkle DAG over the hash dependency relation. A change to a leaf changes the hashes of its transitive dependents only along hash-relevant edges. Unchanged branches retain their hashes.

Canonical serialization MUST exclude presentation-only metadata (display names, source locations, whitespace, timestamps, authorship, and provenance) unless a field is explicitly semantic. The hash is not a proof of behavioral equivalence; it identifies canonical graph content. Hash algorithm identifiers MUST be included in digest representations; SHA-256 is a reasonable initial choice, with algorithm agility.

Hash dependencies MUST be acyclic. Cycles in other SPG relations are allowed only if those relations are excluded from recursive hashing or handled through a separately specified canonical group object.

Specification, Design, and Implementation dependencies MUST be distinguished. An interface-only consumer hashes the provider's Specification state, not its private Implementation state. A consumer that explicitly depends on implementation details hashes the corresponding Implementation state. Build artifact hashes additionally include the relevant compiler/toolchain, build configuration, and target environment.

Mutable labels such as `latest`, branch names, and human-readable release labels are discovery conveniences only. They MUST NOT identify an immutable state, satisfy a dependency lock, or be used as verification inputs.

### 9.2.1 Exact references and approvals

Each semantic object MUST retain a Stable ID and expose an immutable Content Hash for every state. References MUST distinguish:
- a logical Stable ID, resolved only within an explicit snapshot/context; or
- an exact immutable state reference containing both Stable ID and Content Hash.

Approval, verification, and commit records MUST refer to exact Content Hash values. Mutable labels such as `latest`, branch names, or release tags MUST NOT be accepted as proof inputs.

### 9.3 Graph root hashes and accepted snapshots

The project SHOULD identify each coherent graph state by a root Content Hash (or a tuple of layer-root hashes) and each committed state by an immutable accepted snapshot hash.

An accepted snapshot SHOULD commit to the exact roots of:
- Specification Graph;
- Design Graph;
- Implementation Graph;
- linked tests and verification artifacts;
- relevant schema and semantic configuration objects.

Compiler, verifier, runtime, and schema/toolchain releases MAY retain explicit tool versions where their identity is not itself represented as a content hash. The snapshot MUST state the exact mutually consistent layer roots and relevant tool identities.

### 9.4 No destructive history edits

Accepted history, Request originals, Decisions, approvals, and committed snapshots MUST be immutable. Corrections are represented by new content-addressed states or superseding records.

## 10. Lifecycle State Machines

The states below are proposals. Implementations may use different internal encodings if externally observable transition semantics remain equivalent.

### 10.1 Request lifecycle

```text
open
  |-- clarify --> clarifying
  |                  |
  |                  +-- enough information --> ready_for_proposal
  |                  +-- wait for input ------> blocked
  |                  +-- abandon ------------> withdrawn
  |
  +-- already satisfied ---------------------> resolved_no_change
  +-- invalid / out of scope ----------------> rejected

ready_for_proposal
  |-- proposal created --> in_progress
  |-- defer ------------> deferred
  |-- withdraw ---------> withdrawn
```

Suggested Request states:
- `open`: recorded, not yet analyzed;
- `clarifying`: clarification is in progress;
- `blocked`: waiting for a necessary answer or external dependency;
- `ready_for_proposal`: enough information exists to propose changes;
- `in_progress`: one or more Change Sets are active;
- `deferred`: intentionally postponed;
- `resolved_no_change`: no graph change is needed;
- `rejected`: rejected with a recorded reason;
- `withdrawn`: requester withdrew it.

A Request MAY remain open for follow-up Change Sets after one Change Set is committed. Completion semantics for multi-stage Requests are a project policy decision.

### 10.2 Change lifecycle

```text
draft -> proposed -> validated -> in_review
                                  |       |
                                  |       +-> changes_requested -> draft/revised
                                  |       +-> rejected
                                  |       +-> approved
                                  v
                               committed

draft/proposed/validated/in_review -> withdrawn
validated/in_review -> conflicted -> rebased/revised
```

Suggested Change states:
- `draft`: mutable working proposal;
- `proposed`: submitted for validation or review;
- `validated`: structural and required automated checks completed for this revision;
- `in_review`: awaiting human or policy-required review;
- `changes_requested`: reviewer requested revisions;
- `approved`: approved for the exact proposal hash;
- `rejected`: rejected, retained for history;
- `conflicted`: target baseline has incompatible changes;
- `committed`: included in an accepted snapshot;
- `withdrawn`: intentionally abandoned before commit.

A new semantic edit to an approved Change creates a new Change content hash and invalidates the prior approval.

### 10.3 Change Set lifecycle

```text
assembling -> validating -> reviewing -> ready_to_commit -> committed
                  |             |               |
                  v             v               v
               invalid       rejected        conflicted
                  |             |               |
                  +---- revise / rebase / withdraw
```

Suggested Change Set states:
- `assembling`;
- `validating`;
- `invalid`;
- `reviewing`;
- `changes_requested`;
- `rejected`;
- `conflicted`;
- `ready_to_commit`;
- `committed`;
- `withdrawn`.

A Change Set MUST NOT become `ready_to_commit` while required approvals are missing, required checks are stale, blocking questions remain, or conflicts are unresolved.

### 10.4 State transition authority

Transitions MUST be authorized by policy. An LLM may propose a transition but MUST NOT impersonate the human or authority required to perform it.

Automated transitions MAY occur for deterministic events such as validation completion, conflict detection, or commit success.

## 11. Change Operations and Semantic Diff

### 11.1 Structured operations

Changes SHOULD be represented as typed operations over SPG objects, not as unrestricted replacement of large text documents.

Illustrative operations:

```text
AddRequirement(
    id = RequirementId("R-105"),
    parent = FeatureId("order_cancellation"),
    statement = "A cancellation after shipment is forbidden"
)

UpdateContract(
    target = ContractRef("cancel_order.preconditions"),
    add = [order.state != Shipped],
    remove = []
)

AddScenario(
    id = ScenarioId("S-105"),
    verifies = [RequirementRef("R-105")],
    body = Scenario(...)
)

DeprecateRequirement(
    target = RequirementRef("R-102"),
    superseded_by = RequirementRef("R-106")
)
```

Operations MUST declare their target Stable ID + Content Hash or baseline snapshot hash. Preconditions MUST be checked before applying them.

### 11.2 Semantic diff

The review package MUST include a semantic diff with at least:
- added objects;
- removed, deprecated, or superseded objects;
- changed meaning or constraints;
- changed state transitions;
- changed effects and error outcomes;
- changed relationships and dependencies;
- changed acceptance criteria;
- changed verification coverage;
- changes that are syntactic or organizational only.

The system SHOULD distinguish semantic changes from non-semantic refactoring. It MUST NOT classify a change as behavior-preserving solely because the generated code diff looks small.

### 11.3 Before/after behavior

Where behavior changes, the review package SHOULD include examples of:
- behavior before the change;
- behavior after the change;
- newly allowed cases;
- newly forbidden cases;
- unchanged cases;
- failure and boundary cases.

### 11.4 Deletion and deprecation

Deleting a referenced semantic object MUST be rejected unless all required references are removed, redirected, or explicitly marked as historical. Deprecation SHOULD be preferred when external consumers or historical traceability may still rely on the object.

## 12. Approval Policies and Human Authority

### 12.1 Policy-driven approval

The project defines an Approval Policy that maps change classifications and risk levels to required reviewers and checks.

At minimum, policy SHOULD distinguish:
- business-semantic changes;
- public API or compatibility changes;
- security, privacy, or safety-sensitive changes;
- architecture changes with externally observable consequences;
- implementation-only behavior-preserving changes;
- documentation or metadata-only changes.

### 12.2 Default approval matrix

The following is a recommended default, not a universal requirement:

| Change category | Human approval |
|---|---|
| Add, modify, or remove confirmed business rule | Required |
| Change externally observable behavior | Required |
| Change security, privacy, authorization, or data-retention semantics | Required |
| Change public API compatibility | Required |
| Change an assumption into a confirmed requirement | Required |
| Change architecture without business impact | Policy-dependent |
| Behavior-preserving internal refactor | Not normally required |
| Test implementation update with unchanged requirement | Policy-dependent |
| Formatting, generated metadata, or non-semantic documentation | Not normally required |

A project MAY require stricter approval. It SHOULD NOT weaken mandatory approvals for high-impact categories without an explicit policy decision and audit trail.

### 12.3 Approval scope

Approval MUST specify whether it covers:
- specification only;
- design;
- implementation;
- the complete Change Set;
- a particular risk category or deployment boundary.

Approval of a Specification Change does not automatically approve arbitrary implementation details. Approval of an implementation proposal does not authorize changing the approved specification.

### 12.4 LLM authority boundary

An LLM MAY:
- analyze and summarize a Request;
- ask clarification questions;
- propose requirements and decisions for review;
- create and revise Change objects;
- generate Business, Formal, and Scenario views;
- recommend approval requirements;
- explain conflicts and verification failures.

An LLM MUST NOT:
- fabricate a human answer or approval;
- mark an assumption as confirmed without authorized confirmation;
- alter the original Request;
- bypass project approval policy;
- commit a Change Set when required authorization is absent;
- mark an unverified property as proven;
- suppress a failed or unknown check;
- rewrite provenance or historical decisions.

## 13. Atomicity, Isolation, Commit, and Rollback

### 13.1 Proposal isolation

Uncommitted Changes MUST be isolated from the accepted snapshot. They MAY be visible in a working branch or proposal workspace but MUST NOT silently alter the accepted snapshot.

### 13.2 Atomic acceptance

By default, all Changes in a Change Set commit together or none do. If one mandatory operation fails, the Change Set MUST NOT be partially committed.

If a request contains separable work, it SHOULD be split into multiple Change Sets before review, with explicit dependency relationships between them.

### 13.3 Two-phase commit model

A proposed commit protocol is:

**Phase A — Prepare**
1. Verify the baseline.
2. Validate all operations and graph invariants.
3. Resolve conflicts.
4. verify required approvals and approval digests.
5. Verify required tests and evidence are current.
6. Construct the candidate accepted snapshot.
7. Produce a commit plan and digest.

**Phase B — Commit**
1. Atomically compare-and-swap the expected baseline.
2. Persist all immutable graph objects and the accepted snapshot root hash.
3. Record the commit event and provenance.
4. Mark included Changes and Change Set as committed.
5. Publish the new accepted snapshot.

If the baseline changes between prepare and commit, the operation MUST fail with a conflict and require rebase or renewed validation.

### 13.4 Cancellation before commit

A Change Set MAY be withdrawn before commit. Withdrawal does not delete its history or erase generated artifacts. It marks the proposal as no longer active.

### 13.5 Rollback after commit

Rollback MUST NOT rewrite or delete an accepted snapshot. It is a new Change Set that proposes reverting or compensating for a previous accepted change.

The rollback proposal MUST identify:
- the commit being reverted;
- the exact objects and their Content Hash values affected;
- whether the inverse is semantically safe;
- any external side effects that cannot be undone;
- required compensating actions.

The system MUST NOT claim that an external side effect (for example, a payment, email, or physical shipment) has been undone merely because graph state was reverted.

## 14. Concurrency and Conflict Resolution

### 14.1 Baseline and optimistic concurrency

Every Change Set is based on an exact accepted snapshot or declared working revision. Commit uses optimistic concurrency control: the expected baseline must still match or be safely reconciled.

### 14.2 Conflict categories

The system SHOULD identify at least:
- **write-write conflict:** two Changes modify the same object incompatibly;
- **read-write conflict:** a Change relies on an object changed since its baseline;
- **semantic conflict:** separate object edits produce contradictory business rules;
- **dependency conflict:** a required dependency was removed or changed;
- **approval conflict:** approval refers to a superseded proposal or baseline;
- **verification conflict:** evidence was produced against stale inputs.

### 14.3 Automatic merge

Automatic merge MAY be attempted when:
- operations target independent objects;
- operations commute under defined semantics;
- preconditions remain valid;
- no semantic invariant is violated.

Textual non-overlap alone is insufficient evidence that two semantic changes can be merged safely.

### 14.4 Human-assisted resolution

When a conflict affects business meaning, a human decision is required. The system SHOULD show:
- both competing proposals;
- their source Requests and Decisions;
- the common baseline;
- affected requirements and dependencies;
- behavioral consequences of each resolution;
- the proposed merged alternative, if any.

Resolution creates new content-addressed Change states. It MUST NOT silently rewrite either original proposal.

## 15. Dependency Analysis and Verification Invalidation

### 15.1 Dependency graph

The dependency model SHOULD connect:
- Request and Decision records;
- requirements and business rules;
- contracts, types, state machines, and effects;
- Design components and interfaces;
- Implementation objects;
- tests and scenarios;
- proofs and verification results;
- generated artifacts.

### 15.2 Impact analysis

For each Change, the system SHOULD compute:
- directly modified objects;
- transitive dependents;
- potentially affected public interfaces;
- tests that need rerunning;
- proofs whose assumptions changed;
- design or implementation objects that may no longer satisfy their parent layer.

Impact analysis MUST distinguish definite dependencies from heuristic suggestions.

### 15.3 Verification freshness

A verification result is valid only for the exact semantic input Content Hash values and relevant tool/configuration identities against which it was produced.

A result SHOULD record:
- subject object Content Hash values;
- dependency digest;
- verifier/test tool and version;
- configuration;
- execution environment where relevant;
- result status;
- counterexample or evidence reference;
- timestamp and provenance.

If a relevant dependency changes, the result MUST become stale or be explicitly revalidated. A stale `PROVEN` result MUST NOT be presented as current proof.

### 15.4 Partial verification

A Change Set MAY have a mixture of passed, failed, unknown, not-checked, and stale checks. The summary MUST preserve this detail. Policy determines which statuses block acceptance; unknown or not checked MUST never be silently rendered as passed.

## 16. Traceability Requirements

Every confirmed requirement introduced or changed by a Change Set SHOULD link to:
- originating Request;
- confirming Decision or approval;
- acceptance criteria;
- one or more scenarios, tests, or proof obligations appropriate to the requirement;
- Design objects that satisfy it, where Design is used;
- Implementation objects that realize it;
- current verification evidence.

A single test MAY verify multiple requirements. A requirement MAY have multiple verification methods.

A test or proof MUST NOT be treated as evidence for a requirement merely because it is nearby in the graph; the relation must be explicit and validated.

Implementation objects SHOULD link to the requirements and design decisions they realize. Orphan implementation changes that affect externally observable behavior SHOULD be flagged.

## 17. Partial Success and Rejected Proposals

### 17.1 Partial success

A multi-part Request may produce several Change Sets with separate acceptance states. The system MUST show which parts are:
- accepted and committed;
- proposed but not yet accepted;
- blocked;
- rejected;
- deferred;
- withdrawn.

A Change Set itself remains atomic by default. Partial completion is represented by separate Change Sets, not by silently committing a subset of its members.

### 17.2 Rejection

A rejected Change or Change Set remains in history with:
- reviewer and decision;
- rejection reason, if provided;
- proposal digest;
- baseline;
- related Request and Decisions.

Rejection does not imply that the Request itself is rejected. A revised proposal MAY be created.

### 17.3 Changes requested

When a reviewer requests changes, the system creates a new proposal state (with a new proposal hash) or replacement Change. It preserves the reviewed proposal hash and invalidates approvals that no longer apply.

### 17.4 No-op requests

If analysis establishes that the accepted program already satisfies a Request, the system MAY resolve it without a Change Set. It SHOULD provide evidence and identify the existing requirements and verification results that support the conclusion.

## 18. Provenance, Audit, and Reproducibility

The system SHOULD maintain an append-only audit trail for:
- Request creation and amendments;
- clarification questions and answers;
- Decisions and supersessions;
- Change creation and revisions;
- validation and verification runs;
- review decisions and approvals;
- conflicts and resolutions;
- commit, withdrawal, and rollback proposals.

Each event SHOULD include actor, timestamp or sequence, affected object Content Hash values, and causal references.

The system MUST distinguish human, LLM, tool, and system actors. Model identity and relevant tool versions SHOULD be recorded where available, without storing secrets or unnecessary sensitive prompt content.

Reproducibility requires retaining or identifying:
- exact graph root hashes;
- schema/language version;
- compiler and verifier versions;
- relevant configurations;
- test data or reproducible references;
- generated artifact digests.

## 19. Token-Efficient LLM Interaction

This RFC adopts the principles in `TOKEN_EFFICIENCY.md`.

### 19.1 Minimal sufficient context

For each LLM operation, context assembly SHOULD include:
- the Request summary and only relevant original excerpts;
- confirmed Decisions and unresolved questions relevant to the task;
- the target Change and baseline object Content Hash values;
- the minimal dependency subgraph;
- applicable policies and invariants;
- only diagnostics that are new or still unresolved.

The model MUST be able to request additional context when needed. The system SHOULD record which context references and exact Content Hash values were supplied.

### 19.2 Structured patches

LLMs SHOULD return typed graph operations and concise rationale, not full replacement documents, whenever the operation is supported by the structured API.

The system SHOULD validate operation schemas before applying proposals to an isolated working graph.

### 19.3 Incremental diagnostics

Validators SHOULD return stable diagnostic identifiers, affected object IDs, concise explanations, and counterexamples when available. Repeated unchanged diagnostics SHOULD be referenced by ID rather than resent verbatim.

### 19.4 Context cache safety

Cached context and analysis results MUST be keyed by exact object Content Hash values and all hash-relevant dependency hashes. A cache hit MUST NOT be used if any relevant dependency or policy has changed.

### 19.5 Token measurement

The system SHOULD measure per operation:
- input tokens;
- output tokens;
- retrieved context size;
- repeated context;
- diagnostic size;
- number of repair iterations;
- model/tool cost where available.

Token savings MUST be evaluated alongside correctness, review effort, and total cost to reach an accepted result.

## 20. End-to-End Scenarios

### 20.1 Scenario A: New feature

**Human request:** "Allow customers to cancel paid orders before shipment and refund the payment."

1. Create Request `REQ-42`, preserving the original wording.
2. Identify ambiguities: full or partial refund, refund failure, duplicate requests, notification behavior.
3. Ask targeted questions. Record answers as Clarifications.
4. Create Decisions for confirmed choices; keep unresolved matters explicit.
5. Propose requirements, state transitions, and scenarios in Specification Graph.
6. Present Business View and semantic diff.
7. Human approves the specification proposal.
8. Create Design and Implementation Changes linked to the approved requirements.
9. Run structural, type, effect, contract, and scenario checks required by policy.
10. Present impact and verification summary.
11. Commit the Change Set atomically after required approvals.

Expected properties:
- no implementation is accepted against unapproved business meaning;
- every confirmed rule is traceable to the Request and approval;
- failed or unknown checks remain visible.

### 20.2 Scenario B: Change an existing business rule

**Human request:** "Orders may now be cancelled after shipment if they have not been delivered."

1. Create a new Request.
2. Locate the existing rule that forbids cancellation after shipment.
3. Propose a new content-addressed state or superseding rule; do not overwrite history.
4. Analyze dependencies: shipment, delivery, refund, inventory, carrier integration, customer notification.
5. Identify conflicts and missing semantics, such as whether a return shipment is required.
6. Ask the person to resolve blocking questions.
7. Present before/after behavior and affected scenarios.
8. Require human approval because externally observable business behavior changes.
9. Update downstream design, implementation, tests, and proofs.
10. Re-run affected verification and commit a new accepted snapshot.

Expected properties:
- the old rule remains historically accessible;
- the new rule has explicit provenance;
- all affected evidence is refreshed or marked stale.

### 20.3 Scenario C: Proposal rejected

1. LLM proposes a requirement that customers may cancel after shipment.
2. Reviewer rejects it because the business does not support post-shipment cancellation.
3. Record rejection against the exact proposal digest and baseline.
4. Keep the Request open if the user still wants a different solution.
5. The LLM may propose an alternative, such as a return workflow, as a new Change.
6. The rejected proposal remains immutable history and is not included in the accepted snapshot.

Expected properties:
- rejection does not mutate accepted graph state;
- no rejected proposal can be committed accidentally;
- a replacement proposal does not erase the rejection record.

### 20.4 Scenario D: Two concurrent Changes conflict

1. Change Set A modifies the cancellation eligibility rule.
2. Change Set B modifies the order state machine using the same baseline.
3. A commits first.
4. B attempts prepare/commit against the old baseline.
5. The system detects stale baseline and identifies overlapping semantic dependencies.
6. B becomes conflicted; its approval and verification results are not treated as current.
7. The system presents the two changes and their behavioral consequences.
8. An authorized person selects or defines a resolution.
9. A new Change content hash is produced, revalidated, reviewed, and committed.

Expected properties:
- no lost update;
- no silent last-writer-wins for business semantics;
- previous proposals and approvals remain auditable.

### 20.5 Scenario E: Implementation-only change with unchanged business meaning

**Request:** "Replace the internal lookup algorithm to improve performance without changing observable behavior."

1. Create a Request and classify the intended change as implementation-only.
2. Identify relevant confirmed requirements, contracts, public interfaces, and behavior constraints.
3. Propose an Implementation Change without changing Specification Graph.
4. Require evidence that observable behavior remains equivalent to the relevant contracts and tests.
5. Run required tests, static checks, and performance benchmarks.
6. If semantic equivalence cannot be established, flag the uncertainty and escalate to a specification or human review.
7. Commit under the project's implementation-only approval policy.

Expected properties:
- specification remains unchanged;
- implementation links to the requirements it continues to satisfy;
- the system does not infer behavior preservation from code appearance alone.

## 21. System Invariants

The following invariants are normative proposals for this model:

1. **Original intent preservation:** the original Request text is never overwritten by an LLM summary.
2. **No implicit confirmation:** assumptions and inferred facts never become confirmed requirements without authorized confirmation.
3. **Stable identity:** object identity survives renames and ordinary edits.
4. **Immutable content-addressed states:** an existing object state is never modified in place.
5. **Proposal isolation:** uncommitted proposals do not alter the accepted snapshot.
6. **Approval binding:** approval applies only to the exact reviewed semantic proposal and baseline.
7. **No self-approval:** an LLM cannot supply a required human approval.
8. **Atomic Change Set:** a Change Set commits entirely or not at all, unless an explicitly defined alternative transaction model is adopted.
9. **No stale proof:** verification against changed inputs is not presented as current.
10. **No false success:** unknown, not checked, failed, and stale results remain distinct from passed or proven.
11. **Traceability:** confirmed requirements and externally observable implementation changes maintain explicit provenance and links.
12. **Conflict safety:** incompatible concurrent semantic changes cannot be silently overwritten.
13. **Audit preservation:** rejected, withdrawn, superseded, and committed proposals remain historically inspectable.
14. **Rollback by new change:** accepted history is not destructively rewritten.
15. **Authority enforcement:** every state transition and commit is checked against project policy.
16. **Scope transparency:** the review package shows the complete semantic scope of the proposed Change Set, including removals and side effects.

## 22. Acceptance Criteria for This RFC

This RFC is ready for acceptance when reviewers can answer all of the following:

- Are Request, Change, and Change Set boundaries unambiguous?
- Can original human intent be distinguished from confirmed business rules?
- Are assumptions and unresolved questions visible and traceable?
- Can a person review business meaning without reading generated implementation?
- Is the path from Request to accepted graph snapshot explicit?
- Are proposal revisions, approvals, commits, and rollbacks auditable?
- Are lifecycle transitions and authority boundaries sufficiently defined?
- Is Change Set atomicity clear?
- Are stale baselines and semantic conflicts detected?
- Are verification results tied to exact input Content Hash values?
- Can partial Request completion be represented without partial Change Set commits?
- Are LLM token-efficiency mechanisms compatible with correctness and traceability?
- Are all unresolved design choices explicitly listed rather than hidden in implementation assumptions?

An implementation conforming to an accepted revision of this RFC MUST pass scenario tests corresponding to Sections 20 and invariant tests corresponding to Section 21.

## 23. Open Questions Requiring Human Decisions

The following are intentionally unresolved. They should be decided by the project before treating this RFC as an implementation specification.

### 23.1 Product and workflow semantics

1. Can one Request remain active across multiple accepted Change Sets, or should completion normally close the Request?
2. Should a Request be allowed to contain several independent goals, or should the system encourage one coherent goal per Request?
3. Should the system support formal sign-off by multiple roles (for example, product owner and security reviewer), or a configurable reviewer set only?
4. Which change categories require mandatory human approval in the default project policy?
5. Can a project explicitly authorize automatic acceptance of low-risk implementation-only changes?

### 23.2 Specification governance

6. Is every externally observable business rule required to have a human-confirmed Decision?
7. Can requirements be provisionally accepted with explicit assumptions, or must all blocking assumptions be resolved first?
8. Should natural-language and formal representations be edited independently, or should one be canonical with the other generated?
9. What is the minimum required verification coverage for a confirmed requirement?

### 23.3 Identity and storage

10. Should Request and Change objects live inside SPG, in a separate workflow graph linked to SPG, or in a repository-level event model?
11. What Stable ID scheme and canonical hash encoding should be used? Should IDs be opaque, human-readable, or both?
12. Should accepted snapshot hashes identify complete graph roots, commit records, or a combination?
13. What conflict/merge semantics are required for concurrent editing?

### 23.4 Transaction and collaboration

14. Is Change Set atomic commit sufficient, or are cross-Change-Set transactions required?
15. Should approval be role-based, capability-based, policy-based, or a combination?
16. What is the required behavior when an approver becomes unavailable or loses authority after review?
17. Should a committed change be revertible only through a compensating Change Set, or should a specialized revert operation exist?

### 23.5 Verification and implementation

18. Which verification statuses block commit by default?
19. Can a behavior-preserving implementation change be accepted with tests only, or must it provide stronger equivalence evidence?
20. How should the system represent a requirement that cannot currently be formalized?
21. Should the system support release/deployment approvals as a separate layer beyond accepted program snapshots?

### 23.6 Token efficiency and model interaction

22. What is the canonical context package exchanged with LLMs?
23. Should the LLM request additional graph context explicitly, or should the orchestrator infer retrieval from structured references?
24. Which token metrics and cost budgets should be mandatory per Change Set?

## 24. Recommended Initial Decisions

To unblock a first prototype, this RFC recommends the following defaults, subject to explicit project acceptance:

1. Keep Request/Change workflow records logically separate from the three program layers, but link them into the wider semantic provenance graph.
2. Use opaque stable IDs internally and optional readable aliases in the UI.
3. Preserve original Request text verbatim.
4. Require human approval for all changes to confirmed business meaning and externally observable behavior.
5. Make Change Set the atomic unit of review and commit.
6. Use immutable content-addressed object states and accepted snapshots.
7. Use optimistic concurrency with semantic conflict detection; never use silent last-writer-wins for business rules.
8. Treat unknown or stale verification as non-success.
9. Allow multiple Change Sets per Request, with explicit dependency and completion state.
10. Keep implementation-only changes on a lighter policy path when behavior preservation is supported by relevant evidence.
11. Make Business View and semantic diff mandatory parts of review.
12. Start with a small set of structured operations and expand only when real workflows require more expressiveness.

## 25. Conclusion

The proposed Request and Change model makes software development a controlled sequence of semantic decisions and verifiable graph mutations.

The person states intent, resolves meaningful ambiguities, and approves business semantics. The system preserves those decisions as structured Specification Graph objects. LLMs propose local changes to specification, design, and implementation. Independent tools validate the proposals. A Change Set becomes part of the accepted program only after policy, review, baseline, and verification requirements are satisfied.

The core principle is:

**A Request expresses intent. A Specification records confirmed meaning. A Change proposes a semantic mutation. A Change Set makes related mutations reviewable and atomic. An accepted snapshot records what the project has actually approved.**

This model aims to make the business logic understandable to humans, the change process auditable, the implementation independently verifiable, and the LLM interaction efficient without making correctness depend on the model's memory or confidence.
