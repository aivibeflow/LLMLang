# Structure Contracts, Invariant Composition, and Atomic Commit Verification

**Status:** User-confirmed discussion synthesis; candidate design, not yet normative  
**Date:** 2026-11-22  
**Primary research area:** RT-03 — Core language semantics  
**Related areas:** RT-04 (types/effects/ownership/concurrency), RT-06 (dependency semantics and impact), RT-07/08 (formal verification and evidence), RT-19/20 (Toolchain and verified change lifecycle), RT-22/23 (repository/worktree and multi-worktree runtime)

> This document records decisions confirmed in a language-design discussion. It preserves the current direction without claiming that the complete language semantics, proof calculus, runtime protocol, or MCP wire contract has been specified or implemented. Where a detail was not decided, it is explicitly left open.

## 1. Purpose and design direction

The discussion explores a model in which data validity is protected by contracts and formal verification rather than by restricting which functions may access fields.

A structure declares constraints on its admissible state and may also define transition-related rules, including which of its invariants may be checked at a later boundary. Ordinary functions operate on structures explicitly; a function may mutate fields of any structure and may affect multiple structures in one operation. Correctness is established by contract verification at the applicable boundaries, not by private/protected/public access restrictions.

The design is intended to support temporary intermediate states while ensuring that only verified, atomically committed states become externally observable.

## 2. Structures, functions, and contracts

### 2.1 No access-control barrier for invariant protection

- Any function may read or modify any field of a structure.
- Field access restrictions are not the mechanism that protects structural validity.
- Functions may modify several structures, including structures from different modules.
- A function's own contract and the contracts of affected structures are checked according to their respective rules.
- A function cannot unilaterally weaken a structure's verification requirements.

This is not a decision that all implementation details must be public as an API. API visibility and abstraction may be designed separately; they must not be confused with invariant enforcement.

### 2.2 What a structure contract can express

A structure contract may express:
- admissible values and relationships among its fields;
- relationships involving associated or related structure instances;
- permitted state transitions;
- rules that determine which invariant checks may be deferred and to which boundary;
- structure-defined information that controls which recovery or failure-handling alternatives are admissible.

The contract is not limited to a list of field predicates. Transition and deferred-check semantics are part of the candidate model.

### 2.3 Invariant ownership and cross-structure properties

A property involving multiple structures should be declared by the contract that expresses the relevant domain responsibility. For example, consistency between account balances and transaction history may belong to a Transaction contract rather than being assigned automatically to Account merely because account fields participate in the relation.

There is no mandatory unique owner, however: the same invariant may be declared in more than one structure or contract. Duplicate declarations are permitted and are treated as independent contract requirements. A contract may also declare a global/domain invariant whose scope spans multiple instances or structures.

Properties of the external world (for example, whether a remote server is currently reachable or a file exists outside the program's managed state) are not structure invariants. They belong in function preconditions/postconditions or external-interaction contracts.

## 3. Invariant composition and compatibility

### 3.1 Conjunction is the default semantics

All declared invariants must hold simultaneously. No invariant silently overrides, replaces, or cancels another invariant.

If a set of invariants is jointly unsatisfiable, the corresponding program/model is inconsistent. The system must reject a proven contradiction.

### 3.2 Static compatibility checking is fail-closed by default

For each structure or contract, compatibility checking has its own mode. No global default or automatic cross-contract override has been selected.

Default behavior:
1. If compatibility is proved, the program may proceed.
2. If a contradiction is proved, the program is rejected.
3. If neither compatibility nor contradiction can be established, the program is rejected by default.

A contract may explicitly weaken only the compatibility analysis:
- request runtime compatibility checking; or
- disable compatibility checking.

Disabling compatibility checking does **not** disable checking whether each individual invariant holds. Individual invariant enforcement remains governed by its own verification and check-boundary rules.

When the same condition is declared in multiple contracts, each declaration uses the compatibility-checking mode of the contract containing that declaration. The declarations are not merged into one declaration and do not inherit a common strongest or weakest mode.

### 3.3 Duplicate declarations and logical analysis

- Duplicate or logically equivalent invariant declarations are a supported language feature, not a warning condition.
- Invariant identifiers are not required; an invariant is expressed by its condition.
- The checker should attempt to recognize logical equivalence even when conditions have different syntax.
- The checker should also attempt to establish logical implication between invariants. For example, balance >= 100 implies balance >= 0.
- Proven equivalence or implication may be used for proof reuse and to avoid redundant computation, but must not erase declaration provenance or alter per-contract settings.
- If equivalence cannot be proved, declarations are treated as independent and both remain subject to checking. Failure to prove equivalence is not itself an error.

### 3.4 One global dependency graph

The analysis model uses one global graph containing both:
- logical relationships between invariants (equivalence, implication, incompatibility, and other proved relations); and
- dependencies from data/fields and semantic operations to invariants that may be affected by their changes.

The graph is global so that dependencies crossing contract and structure boundaries can be discovered. This does not merge invariant declarations, contract ownership, or verification settings.

The graph must be conservative. If the system cannot prove that a data change is unrelated to an invariant, it must treat that invariant as potentially affected and must not omit the required check.

## 4. Mutation, deferred checks, and commit

### 4.1 Temporary intermediate states

A function may temporarily place one or more structures in states that violate invariants while it performs a multi-step transformation. The structure contract determines which of its invariants may be deferred and the boundary at which each deferred invariant must be checked.

Different invariants of the same structure may have different check boundaries. For example:
- a local safety condition such as balance >= 0 may be required after each function;
- a parent/children consistency condition may be deferred until the enclosing operation completes;
- a graph-wide acyclicity condition may be deferred until the transaction that changes the graph commits.

A function cannot invent a deferral that the relevant structure contract does not permit.

### 4.2 Commit is a consistency boundary

Commit is a logical boundary at which the system must establish consistency of the complete affected state. The affected verification scope includes:
- directly modified structures;
- related structures whose contracts may be affected;
- global invariants whose declared scope intersects the changes;
- the function/operation contract and other applicable obligations.

The system should avoid blindly traversing every reachable object. It should determine the affected set from contract scope and the dependency graph, while conservatively including an invariant whenever non-impact cannot be proved.

### 4.3 Graph construction and proof timing

The global dependency graph is built or updated and its required properties are proved when changes are committed. This is not merely a compile-time-only graph construction step.

The exact persistence and reuse policy for graph fragments and proof artifacts between commits has not yet been decided.

### 4.4 Atomicity

Commit is all-or-nothing:
- either all changes in the commit become visible, or none do;
- if verification fails, the candidate changes are not published and the pre-commit state remains;
- external observers, including concurrent computations, must not observe intermediate invalid states;
- concurrency control must preserve the atomic visibility of committed changes.

This describes the logical contract. The concrete memory model, synchronization protocol, rollback mechanism, and storage implementation remain to be specified.

## 5. External side effects

A local state transition may temporarily violate an invariant while it is being prepared. Irreversible external effects (for example, network requests, external writes, or sending messages) must not normally occur before the resulting state has passed the required verification, because they may not be rollbackable.

The default candidate sequence is:

1. Prepare local changes and stage external effects.
2. Build/update the affected dependency graph.
3. Verify applicable invariants, compatibility requirements, and operation contracts.
4. Atomically publish the local state and release the permitted staged effects.

An explicit opt-in may permit an external effect before the normal verification boundary, but it must carry additional correctness obligations. The language/runtime must not claim atomicity between local state and an arbitrary external system unless a specific protocol provides it.

## 6. Workflows, worktrees, and integration

The discussion aligns the language-level commit model with the existing LLMLang Toolchain research:

- Parallel commits are permitted only in different workflows.
- Each parallel workflow uses its own isolated Git worktree for ordinary repository files.
- Worktree isolation does not imply a separate semantic object store or a separate Toolchain Server; the existing RT-23 shared immutable semantic-state model remains applicable.
- Integration of changes from different workflows is a separate operation, not an implicit side effect of either workflow's commit.
- Integration is itself a consistency boundary and must verify the combined result.
- The preferred verification strategy for integration is incremental: recheck affected contracts/invariants and reuse prior evidence only when the system proves that it remains applicable. If non-impact cannot be proved, perform the additional check.

The exact relationship between a language-level semantic commit, a Toolchain Change Set/Snapshot acceptance, export to a worktree, and creation of a Git commit must follow RT-19/20/22/23. This document does not redefine those APIs or lifecycle states.

## 7. Illustrative example

The following is schematic, not proposed final syntax:

~~~text
struct Account {
    balance: Int

    invariant balance >= 0
}

contract Transaction {
    invariant account.balance ==
        initial_balance(account)
        + credits(account)
        - debits(account)
}
~~~

A transfer function may update two accounts and append a transaction record. Intermediate values may temporarily violate deferred cross-object consistency rules. At the applicable commit boundary, the system checks the account-local invariant, the transaction consistency invariant, and any other affected contracts. All must hold together before the result is published.

The same transaction consistency condition may also be declared in another relevant contract. The declarations remain independent requirements; proven logical equivalence can reduce repeated proof work without merging their settings or provenance.

## 8. Decisions confirmed in the discussion

| Topic | Confirmed direction |
|---|---|
| Field access | Any function may modify any structure field; no access modifier is used to enforce invariants |
| Function scope | One function may modify multiple structures |
| Intermediate states | Temporary invariant violations are allowed within a function/operation where the structure permits deferred checks |
| Contract scope | Structure contracts can define admissible states, transitions, and deferral rules |
| Cross-structure invariants | Use the appropriate global/domain contract; invariant declarations may be duplicated |
| External-world facts | Not structure invariants |
| Invariant composition | All invariants must hold simultaneously |
| Contradictions | Proven unsatisfiable combinations are rejected |
| Unknown compatibility | Reject by default; explicit per-contract weakening may request runtime checking or disable compatibility analysis |
| Individual checks | Remain active even when compatibility analysis is disabled |
| Duplicate declarations | Allowed without warning; no mandatory invariant IDs |
| Logical analysis | Attempt equivalence and implication; unknown equivalence means independent checks |
| Dependency model | One global graph for logical and data dependencies |
| Graph timing | Build/update and prove at commit |
| Commit semantics | Atomic all-or-nothing publication |
| Parallel work | Parallel commits only across different workflows; each workflow has a separate worktree |
| Cross-workflow integration | Separate operation with incremental re-verification |

## 9. Open questions and boundaries

The discussion has not yet selected:
- the concrete syntax and formal semantics for structures, contracts, invariant declarations, and transition rules;
- the proof calculus/solver architecture and the exact meaning of runtime compatibility checking;
- how an invariant's declared scope is represented and how the affected instance set is computed;
- the exact semantics of nested function boundaries and transaction boundaries;
- the concrete synchronization, isolation, rollback, and publication implementation;
- how staged external effects are represented, retried, compensated, or coordinated with local commit;
- whether graph fragments and proof artifacts are persisted and reused across commits;
- the exact mapping from semantic commit to Toolchain Snapshot acceptance and Git commit lifecycle.

These items must be resolved against RT-03, RT-04, RT-06, RT-07/08, RT-19/20, and RT-22/23 rather than being silently decided by this synthesis.
