# RT-16 — Threat model for agent-proposed changes

**Status:** Initial threat model and executable authorization experiment. The policy model is bounded and does not define production credentials, approval, sandbox, or signature formats.

## 1. Scope and assets

This study follows one change through a Toolchain Server, verifier, repository, package publisher, and runtime. It treats the model and all model-originated text as untrusted. Assets include accepted source state, credentials, execution hosts, reusable build and proof evidence, package artifacts, and the authority to accept, commit, push, or publish.

### Principals

- A **human reviewer** resolves requirement ambiguity and grants approval under project policy.
- An **agent** inspects and proposes changes within delegated capabilities.
- A **toolchain service** validates identities, applies proposals, and records lifecycle state.
- A **verifier** runs declared checks and records evidence for exact inputs.
- A **builder or runtime** executes repository code and external dependencies.
- An **artifact provider** supplies source, packages, tools, and reusable evidence.

These roles may share infrastructure. Authorization still needs attributable principals and explicit authority for each privileged operation.

### Boundaries

1. Model prompt and retrieved repository/package content enter an untrusted inference boundary.
2. Structured proposals enter the Change Engine, which checks schema and expected base identity.
3. Build, test, proof, and solver jobs run untrusted code and parsers across an execution sandbox boundary.
4. Evidence moves from the verifier to acceptance policy, where input identities and producer are checked.
5. Acceptance, Git export, commit, push, and package publication cross separate authority boundaries.
6. Cache, object-store, registry, and dependency-provider responses cross provenance and integrity boundaries.
7. Runtime capabilities cross from language code into host operations.

## 2. Threat actors and assumptions

Consider a malicious or compromised model, repository or package author, dependency provider, build script, stale or buggy checker, compromised worker, replaying client, confused deputy, and a user who grants excessive scope. An attacker may control request text, repository content, package payloads, build scripts, test data, and retry timing. The attacker may exploit concurrency between authorization and execution.

The prototype assumes the policy evaluator, trusted clock, and request construction are correct. Its in-memory nonce ledger is single-process state. It does not model identity-provider compromise, distributed transaction failure, signature cryptography, or OS sandbox escape. Passing its tests establishes only the modeled decision properties.

## 3. Abuse cases and required controls

| Threat | Attempt | Required control | Testable failure |
|---|---|---|---|
| Prompt injection through source or package docs | Retrieved text asks the agent to ignore scope, disclose secrets, or invoke privileged tools. | Treat retrieved text as data. Enforce authorization in the service for each operation. | Text cannot grant a capability or approval. |
| Confused deputy | An agent uses a valid grant for another actor, repository, or workspace. | Bind capabilities to principal, repository/workspace, action, and optionally base revision. | Any mismatched scope is denied before mutation. |
| Stale proposal | Base moves after review or verification. | Compare expected base revision at apply, accept, and repository synchronization. | Stale base prevents acceptance or commit and triggers re-analysis. |
| Approval substitution | Approval for one tree or action is replayed for another. | Bind approval to action, repository, exact base revision, target digest, expiry, and unique nonce. | Any changed binding is rejected. |
| Approval replay or race | Two requests use one approval concurrently. | Atomically reserve a nonce before side effects and consume it on success. | Only one concurrent request reserves the approval. |
| LLM self-approval | Model-generated prose claims a user approved commit or publication. | Approval comes from an authenticated human or independent policy principal. | Agent identity cannot satisfy human approval. |
| Verification bypass | Agent requests acceptance with failing, stale, missing, or self-produced tests. | Acceptance checks required evidence and provenance against exact candidate/tool/config identities. | Missing, stale, unknown, or untrusted evidence cannot satisfy a required gate. |
| Cache or proof replay | Reuse follows a source, tool, target, assumption, or checker change. | Evidence identity commits to every behavior-relevant input and verifier identity. | Mutating any committed input invalidates reuse. |
| Malicious build/test content | Scripts exfiltrate secrets, modify unrelated state, or persist between jobs. | Ephemeral isolated workers, no ambient credentials, explicit network/filesystem grants, resource limits, and cleanup verification. | A job cannot access another workspace or secret by default. |
| Package substitution | Provider serves bytes or metadata different from the requested identity. | Recompute content identity. Validate signed provenance and publisher policy separately from hash equality. | Mismatched bytes or unauthorized publisher are rejected. |
| Runtime capability escalation | Program uses ambient filesystem, network, process, or clock access. | Explicit capabilities enforced by runtime and OS boundary. | Undeclared operation fails and creates an audit event. |
| Partial commit or crash | Acceptance, export, commit, and push disagree after interruption. | Record separate recoverable states and make operations idempotent under a stable request identity. | Recovery reports pending synchronization and never claims an unperformed push. |

## 4. Authorization prototype

The experiment is in [authorization policy model](PROTOTYPES/RT-16-AUTHORIZATION-01/policy.py). A grant names the principal, repository, allowed operations, and optionally an exact base revision. Approval-sensitive actions require a human principal's approval bound to action, repository, base revision, and target digest, with expiry and nonce. A ledger models one-time nonce reservation and consumption across retries.

The same prototype checks required verification records against candidate, toolchain, target, and assumption identities, the verifier identity, and an exact passed result. Its deterministic SHA-256 digest commits to those record fields so that mutations change the digest. A digest alone cannot establish who produced a record. Verifier authentication, signatures, and the trusted source of the expected digest remain outside this experiment.

Run the finite decision fixtures with:

```sh
python3 -m unittest discover -s research/PROTOTYPES/RT-16-AUTHORIZATION-01 -p 'test_*.py' -v
```

The 24 fixtures cover exact authorization, cross-principal and cross-repository use, stale base, action separation, target substitution, agent self-approval, expiry, replay, non-privileged validation, nonce reservation, and releasing a reservation after failure. Evidence fixtures cover missing, duplicate, failed, unknown, stale, and untrusted records, plus evidence digest sensitivity to producer and result. They do not establish production security, concurrent storage correctness, or cryptographic approval/evidence authenticity.

## 5. Security decisions that remain open

- Whether human approval is required by human policy, project policy, or both for acceptance, commit, push, publication, and deletion.
- Whether approval may be delegated and how delegation depth, expiry, revocation, and audit identity work.
- Which scopes can be granted to agents, including whether repository and object subpaths are sufficient isolation units.
- How evidence producers are authenticated and which checker/toolchain versions require signatures or independent reproduction. The prototype digest is unkeyed and does not authenticate a producer.
- How sandboxes handle network, secrets, compiler caches, persistent workers, and hostile resource exhaustion.
- How policy and grants are versioned and recorded without making them semantic source identity.
- How commit/push survives concurrent base movement and distributed failure while preventing side effects before authorization.

The prototype uses explicit exact bindings and one-time nonces to expose replay and scope failures. Repository maintainers still need to select who can approve each lifecycle action.

## 6. Exit criteria and next experiments

1. Test the abuse cases against a persistent, multi-client authorization store.
2. Run concurrent reservation and crash-injection tests around commit and publication side effects.
3. Test authenticated, signed evidence by varying source, toolchain, target, environment assumptions, and verifier identity independently. The current fixtures test identity matching and digest sensitivity only.
4. Attack build workers with workspace traversal, secret discovery, network egress, process persistence, and resource exhaustion fixtures.
5. Test package identity and publisher provenance as separate checks, including revoked keys and provider equivocation.
6. Compare policy decisions and recovery records across two independent client adapters.

The model constrains authority claims in RT-19 and RT-20. It does not determine which source-language execution profile is preferable.

## 7. References

- [RT-19 Toolchain Server](RT-19-TOOLCHAIN-SERVER-AND-SEMANTIC-DEVELOPMENT-API.md) separates acceptance, commit, push, and publication boundaries.
- [RT-20 patch planning](RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md) models planned changes and verified commit workflow.
- [Global semantic artifact store](GLOBAL-SEMANTIC-ARTIFACT-STORE.md) distinguishes content identity from compatibility and trust.
- [RT-01 reference workloads](RT-01-REFERENCE-WORKLOADS.md) defines agent change acceptance and human review measurements.
