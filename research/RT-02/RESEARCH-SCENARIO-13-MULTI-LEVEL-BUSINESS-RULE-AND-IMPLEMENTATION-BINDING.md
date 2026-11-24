# Research Scenario 13: Multi-Level Business-Rule and Implementation Binding

**Status:** Research / exploratory; not normative.  
**Date:** 2026-11-16  
**Predecessors:** Scenarios 09–12; Dependency Graph Prototype 01.

## Executive conclusion

A project → tenant → request precedence chain is useful, but it is not a sufficient semantic model. It answers which candidate wins, not whether the winning candidate is allowed to replace the previous one without changing program meaning.

The central distinction is:

1. **Implementation binding:** choose one implementation among implementations that satisfy the same behavioral contract. If conformance is established, the caller's specified behavior remains unchanged. The resolved implementation still matters to build/deployment/execution identity and verification evidence.
2. **Business-policy selection:** choose which business rule applies (for example, a 15% or 20% tax regime). This is not a transparent implementation substitution. It is a semantic input or an explicit policy decision. It must be visible in the caller's requirements/contract or in the caller's explicit inputs, and it must be pinned in the relevant snapshot.

A type-compatible implementation is not necessarily behaviorally equivalent. An implements edge is a declaration, not a proof. A runtime override must never silently turn a change in business policy into what appears to be a harmless implementation swap.

**Preliminary recommendation:** keep the caller dependent on a behavioral contract; resolve implementations through an explicit, versioned binding policy; represent business-policy choice as an explicit semantic value/input; record the complete resolution decision (including scope, policy, consulted snapshot roots, and winning target) in an immutable resolution snapshot. Do not treat the simple precedence algorithm as authorization or proof of semantic substitutability.

## 1. Research question and motivating example

Consider a caller:

invoice_total → TaxPolicy contract → selected implementation.

The implementation may be selected at:
- project scope (default for the application);
- tenant scope (customer-specific configuration);
- request scope (a narrowly authorized per-request choice).

A naïve rule says request overrides tenant, tenant overrides project. That rule is deterministic only if all inputs are pinned, and safe only if every override is semantically permitted.

Suppose the project binds TaxPolicy to implementation tax_standard, a tenant binds it to tax_reduced, and one request binds it to tax_exempt. These might be:
- three equivalent algorithms that compute the same specified tax result;
- three legally distinct tax policies with different outputs.

The first case may be implementation binding. The second is business-policy selection. Treating both as one mechanism hides a semantic decision.

## 2. Four different objects

### 2.1 Behavioral contract

A contract defines caller-observable behavior, not merely a function signature:
- input and output domains;
- preconditions and postconditions;
- invariants;
- permitted effects and failure behavior;
- relevant ordering, rounding, precision, and boundary semantics;
- any explicitly permitted variation.

For a tax calculation, a contract that says only Money → Money is far too weak to prove interchangeable tax implementations. If the tax rate is intentionally variable, the contract must expose the policy/rate as an input or explicitly describe the permitted variation.

### 2.2 Implementation

An implementation is a semantic value that claims to satisfy a contract. Its implements dependency identifies the claimed contract, but the edge alone is not conformance evidence.

Conformance evidence must be separate and pinned to:
- exact implementation hash;
- exact contract hash;
- verifier/proof method and version;
- assumptions and configuration;
- relevant dependency closure.

A binding resolver may reject a candidate whose declared contract differs from the caller's expected contract. It must not infer behavioral conformance from matching types or from the existence of an implements edge.

### 2.3 Binding policy

A binding policy defines:
- which scopes exist;
- their precedence;
- which scope-to-scope overrides are allowed;
- which keys/contracts may be overridden;
- who may publish each layer;
- whether a missing binding is an error or a defined fallback;
- whether a request may select an implementation at all;
- whether selection is static, deployment-time, or request-time.

Precedence and permission are separate. A more specific scope does not automatically have authority to override a less specific one.

### 2.4 Resolved binding

A resolved binding is the result of evaluating the policy against a specific set of immutable layer snapshots and context. It should record:
- binding key and expected contract hash;
- chosen implementation hash;
- winning scope and scope identity;
- binding policy hash;
- roots of all consulted scope snapshots (including layers where the key was absent);
- resolver identity/version;
- resolution context identity, without leaking raw personal data.

This record makes the choice auditable and reproducible. It is not enough to record only the final implementation hash: the same target may have been selected under different authority, policy, or tenant context.

## 3. Scope precedence is not semantic equivalence

A possible default precedence is project < tenant < request. This is only a resolution order. It must be accompanied by an explicit override matrix. For example:

| Existing binding | Proposed override | Default research position |
|---|---|---|
| project | tenant | Allowed only by policy |
| project | request | Deny by default; explicit capability required |
| tenant | request | Deny by default; explicit capability required |
| same scope | same scope | New immutable layer revision; conflict/review rules apply |

A policy may permit tenant overrides but prohibit request overrides. Another system may allow request-level canary routing only among a pre-approved set of equivalent implementations. The language must represent these as policy, not rely on convention.

A request-scope override should be treated as untrusted input until authenticated and authorized. Tenant identity must be derived from trusted authentication context, not accepted from arbitrary request payload fields. The resolver itself does not establish that the caller is authorized to use a particular tenant layer.

### 3.1 No implicit fallback on errors

These states must remain distinct:
- no binding exists;
- candidate exists but contract mismatches;
- candidate exists but is not authorized to override;
- candidate exists but conformance evidence is absent/stale;
- resolution is ambiguous or malformed.

A mismatch or authorization failure must not silently fall back to a lower-precedence implementation. Such fallback can conceal configuration errors and bypass policy. Fallback is valid only when explicitly specified as a policy rule and recorded in the resolution result.

## 4. Implementation choice versus business-policy choice

This is the most important semantic boundary.

### 4.1 Safe implementation substitution

Suppose two implementations satisfy the same sufficiently strong contract:

tax_impl_a : TaxPolicyContract  
tax_impl_b : TaxPolicyContract

If the verifier establishes that both satisfy the same contract under the same assumptions, changing the binding does not change the caller's specified behavior. The caller's semantic value can remain unchanged.

However:
- the BindingSnapshot changes;
- build/deployment/execution roots change at the layer where the binding is consumed;
- verification records tied to the exact implementation or binding must be recomputed or looked up under a new exact key;
- old executions remain pinned to their previous resolved binding.

The phrase "caller semantics unchanged" is conditional on the contract actually constraining all caller-observable behavior. A weak contract cannot support this claim.

### 4.2 Business policy is a semantic input

Suppose one tenant legally uses a 15% rate and another uses 20%. Those values do not satisfy one identical deterministic tax behavior unless the policy is an explicit input.

A better semantic shape is:

calculate_tax(amount, policy) -> TaxResult

where policy is an immutable, typed semantic value with its own hash and provenance. The caller's requirements specify which policy is appropriate, or explicitly delegate policy selection to a named authority. A tenant/request policy choice is then visible in:
- the caller's explicit input/requirement model;
- the policy value hash;
- the relevant tenant/request resolution record;
- the ExecutionSnapshot.

The function implementation can still be substituted independently, provided it conforms for every allowed policy input.

This aligns with the project principle that business rules arise from the place where a function is used: the caller must express what tax semantics it needs. A lower-level function should not silently invent or choose a different business rule merely because a binding override exists.

### 4.3 Delegated policy decisions

Sometimes the caller intentionally says: "Use the tax policy assigned by the authenticated tenant." That is still an explicit business rule. It delegates selection to an authority.

The semantic caller must identify:
- the policy contract/type;
- the authority responsible for selection;
- allowed policy domains or constraints;
- whether request-level override is permitted;
- what happens when no valid policy is available.

The actual selected policy becomes a runtime semantic input and must be captured in the execution record. The delegated selection rule belongs to the caller's semantics even if the policy value is resolved outside the source code.

## 5. When binding is resolved

| Resolution time | Typical examples | Identity impact |
|---|---|---|
| Compile/build time | static provider, compiler plugin, generated code | BuildSnapshot |
| Deployment time | environment-specific service implementation | DeploymentSnapshot |
| Request/execution time | tenant-specific provider, per-request canary | ExecutionSnapshot / per-call resolution record |

These are not interchangeable.

A build-time binding should be fixed before build output is produced. A deployment-time binding changes deployment identity even if the binary is unchanged. A request-time binding may vary between calls under one deployment, so the selected binding must be captured per execution or per relevant call.

If a single execution resolves the same contract more than once and the binding can change mid-execution, pin a resolution snapshot at the required consistency boundary (for example, request start or transaction start). Do not allow one logical operation to observe a mixture of binding versions unless that behavior is explicitly specified.

## 6. Hash and dependency consequences

### 6.1 Keep identity layers separate

The existing layered identity model remains useful:

- ProjectSnapshot: source semantics, including caller requirements and explicit policy-selection rules.
- BuildSnapshot: exact project plus build-time binding resolution.
- DeploymentSnapshot: exact build artifact plus deployment-time bindings and configuration.
- ExecutionSnapshot: exact deployment plus request/tenant binding resolution, policy values, inputs, and external observations.

A tenant/request binding should not mutate the ProjectSnapshot. But it must not be omitted from the execution identity when it can affect behavior.

### 6.2 ResolvedBindingSnapshot hash inputs

A candidate canonical record should include:
- domain/version tag;
- binding policy hash;
- expected contract hash;
- chosen implementation hash;
- winning scope and a privacy-safe scope identity commitment;
- ordered roots of all consulted layer snapshots;
- resolver identity/version;
- resolution-context commitment (only fields that affect selection).

Including consulted layer roots is conservative: even a change in a layer that did not contain the selected key can invalidate the resolution record. A later optimization may use a minimal proof of the exact lookup path, but it must prove that omitted state could not have changed the result.

Do not hash raw tenant/user identifiers if that creates privacy or dictionary-attack risks. Use protected opaque references or keyed commitments under a documented threat model. The identity must still distinguish contexts that can resolve differently.

### 6.3 Avoid contaminating caller hashes

If the caller calls a contract and its business behavior is fully constrained by that contract, do not put a concrete implementation hash into the caller's semantic value. That would cause unnecessary caller churn for a valid implementation replacement.

If the caller chooses a business policy, or the policy is part of the caller's required behavior, that policy selection/value must be a semantic dependency or explicit input. Do not hide it in an implementation binding.

## 7. Impact analysis

| Change | Expected impact |
|---|---|
| Contract behavior changes | Callers, implementations, conformance evidence, dependent verification |
| Implementation body changes, contract unchanged | New implementation hash; conformance evidence for new hash; bindings selecting it; affected builds/deployments/executions |
| Binding policy precedence/authority changes | All resolutions whose lookup result or authorization may change; affected execution/deployment snapshots |
| Project binding changes | Build snapshots and downstream artifacts/deployments |
| Tenant binding changes | That tenant's future resolution/execution snapshots; no unrelated tenant's state |
| Request binding changes | Only the affected request/execution, subject to authorization |
| Business-policy value changes | All callers/executions that consume that policy value; impact follows semantic dependency/selection graph |
| Conformance proof expires or verifier changes | Evidence status changes; dependent verification may become UNKNOWN/NOT_CHECKED until re-established |

The dependency graph must distinguish:
- semantic dependency on a contract;
- implementation's conformance claim;
- binding-policy dependency;
- resolved binding decision;
- explicit business-policy input;
- provenance and authority records.

These relations have different invalidation behavior and should not be collapsed into one generic depends-on edge.

## 8. Tenant isolation and security

Multi-tenant resolution has two separate concerns:
1. deterministic selection of a tenant's configuration;
2. authorization and isolation preventing one tenant from reading or influencing another tenant's binding.

The resolver should receive a tenant scope selected by trusted authentication/authorization infrastructure. It should not trust a user-supplied tenant key without validation. Cache keys must include tenant identity and the exact configuration snapshot root. A cache keyed only by binding name or implementation hash can accidentally reuse another tenant's resolution.

The same applies to request scope: request overrides need explicit capabilities, allowed-key constraints, and audit records. A request should not be able to override arbitrary contracts simply by supplying a matching key.

## 9. Existing ecosystem evidence

### OpenFeature

OpenFeature specifies evaluation context and explicitly describes context levels and merge precedence. Its specification gives a precedence order from global API context through transaction, client, invocation, and hooks, with later contexts overriding duplicate fields. This demonstrates that layered context merging is a real and standardized pattern.

However, OpenFeature's context merge is not proof that a chosen implementation is behaviorally equivalent to another. Context/flag evaluation and semantic implementation substitution are different problems. LLMLang needs the additional contract/conformance boundary described above.

Source: https://openfeature.dev/specification/sections/evaluation-context/

### Azure App Configuration

Microsoft's multitenancy guidance distinguishes shared settings from tenant-specific settings, discusses tenant partitioning and caching, and describes tenant-scoped snapshot references for independent rollout/rollback. This supports pinning tenant configuration to immutable snapshot references rather than looking up mutable individual values during replay.

Source: https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/service/app-configuration

### AWS AppConfig

AWS AppConfig deployment records include application, environment, configuration profile, configuration version, and deployment strategy. The selected configuration version is an explicit deployment input. This is a useful precedent for treating environment configuration as versioned deployment state rather than ambient mutable state.

Source: https://docs.aws.amazon.com/appconfig/latest/userguide/appconfig-deploying.html

These systems provide useful configuration patterns, not a ready-made formal model for LLMLang's semantic guarantees.

## 10. Prototype extension

Added an experimental scoped resolver in src/scoped_binding.py.

The prototype models:
- immutable project, tenant, and request binding layers;
- explicit precedence;
- an explicit allowed-override matrix;
- exact contract matching;
- implementation kind and declared implements relation checks;
- resolution snapshots that pin the binding policy, consulted layer roots, winning scope, scope identity commitment, selected implementation, and resolver version.

Tests cover:
- request > tenant > project precedence;
- rejection of an override not authorized by the matrix;
- rejection of contract mismatch;
- tenant identity commitment affecting resolution identity;
- a changed consulted layer producing a different resolution root;
- deterministic resolution independent of input row ordering.

The prototype intentionally does not claim to prove behavioral conformance. It checks structural declarations only. It also does not authenticate tenant identities, enforce capabilities, implement distributed storage, or resolve business-policy values. Those remain separate responsibilities.

## 11. Preliminary recommendations

Research direction, not normative:

1. Preserve the distinction between behavioral contracts and concrete implementations.
2. Treat implements as a claim; require independently verifiable conformance evidence before calling an implementation substitutable.
3. Use project → tenant → request only as a configurable resolution hierarchy, never as implicit authority.
4. Require an explicit override matrix and default-deny request-level overrides.
5. Do not silently fall back after contract, authorization, or evidence errors.
6. Make business-policy selection explicit at the caller boundary or an explicitly delegated authority boundary.
7. Represent policy values as immutable semantic values/inputs, not as interchangeable implementation bindings.
8. Pin the resolved binding at the scope where it can affect behavior: build, deployment, or execution.
9. Include consulted snapshot roots, policy identity, winning scope, and privacy-safe context identity in the resolution record.
10. Keep tenant identity and authorization outside untrusted request payloads; isolate caches by tenant and exact snapshot.
11. Preserve old resolution and execution records so historical behavior can be reconstructed.
12. Keep this as research until further scenarios and prototype tests validate the model.

## 12. Open questions

- Should a binding policy be a semantic graph node, a deployment policy, or both depending on its scope?
- What exact proof object should certify behavioral contract conformance?
- How are nondeterministic or probabilistic implementations constrained?
- Can one contract explicitly permit a set of policy variants, or should policy always be a separate input?
- What is the smallest lookup-proof record that permits safe cache reuse without hashing every consulted layer root?
- How should authorization revocation affect replay of historical executions versus permission to start new executions?
- What is the consistency boundary for request-level resolution: request, transaction, individual call, or explicit user-defined scope?

## Public-interface integration (2026-11-24; proposed)

Resolve the public name to an exact operation before applying scoped provider selection. A tenant/request override cannot silently change the public operation revision or business-policy contract. If the public contract explicitly leaves a policy parameter variable, pin the selected value as a semantic input; otherwise use an explicit new operation revision or migration. Require exact provider-contract refinement, body correctness and scope authorization for each winning provider. A conforming implementation need not produce identical traces to another unless the public contract guarantees that.

Related: [Public interfaces and verified contract refinement](../RT-05/PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md). This follow-up does not change earlier results or accepted rules.
