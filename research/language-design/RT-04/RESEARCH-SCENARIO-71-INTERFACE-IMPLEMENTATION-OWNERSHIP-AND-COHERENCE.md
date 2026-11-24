# Research Scenario 71 — Interface Implementation Ownership and Coherence

**Status:** Evidence-linked prior-art comparison; no LLMLang conformance/instance policy selected  
**Research area:** RT-04 generics/dispatch, RT-09 type checking, RT-20 modular evolution  
**Updated:** 2026-11-19

## 1. Question and scope

Who may declare that a type implements an interface/trait, how are duplicate or overlapping implementations prevented or selected, and where does the implementation become visible? These rules affect ambiguity, dependency upgrades, separate compilation, extension libraries, and whether adding an interface requirement can silently change behavior. This study complements Scenario 42's broad generics/dispatch comparison by isolating implementation ownership and coherence.

## 2. Prior-art comparison

### Rust: explicit impls, orphan restrictions, and overlap rejection

Rust requires explicit trait implementations. Coherence rejects an implementation if it violates orphan rules or overlaps another implementation. The orphan rule generally requires the trait or a relevant type to be local to the crate, with ordered uncovered-parameter rules for generic heads. This assigns authority to the trait/type owner and protects downstream users from independently choosing conflicting implementations when dependency graphs evolve. The restriction can require a local wrapper when integrating two foreign abstractions.

Source: [Rust Reference — Implementations and coherence](https://doc.rust-lang.org/reference/items/implementations.html).

### Go: implicit structural satisfaction, no global impl declaration

Go interfaces are satisfied implicitly when a type's method set contains the required methods. There is no separate conformance declaration to own or import, so independently authored interfaces can be satisfied by the same type without selecting a global implementation instance. This permits local, consumer-defined interfaces and loose coupling. It also means conformance can arise accidentally, method-set details (including pointer/value method sets) matter, and changing an interface's required methods changes which types satisfy it.

Sources: [Go Specification — Implementing an interface](https://go.dev/ref/spec#Implementing_an_interface), [Go Specification — Method sets](https://go.dev/ref/spec#Method_sets).

### Swift: explicit protocol conformance and retroactive extension

Swift records explicit protocol conformances, which can be declared in an extension of an existing type. A concrete type cannot have duplicate conformances to the same protocol; redundant and conflicting declarations are diagnosed. Declaring conformance for a type and protocol owned by other modules is retroactive: it can conflict if an owner later adds the same conformance. Current Swift documentation/compiler design warns about this risk and offers an explicit `@retroactive` marker. Thus explicit conformance supports discoverability and witnesses, while ownership and binary/runtime visibility still matter.

Sources: [Swift Language Reference — Declarations and extensions](https://docs.swift.org/swift-book/ReferenceManual/Declarations.html#Extensions), [Swift Generics — Conformance Lookup](https://download.swift.org/docs/assets/generics.pdf), [Swift Evolution SE-0364 — Retroactive Conformance Warnings](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0364-retroactive-conformance-warning.md).

### Haskell: global type-class instances, orphan costs, and overlap controls

Haskell type-class instances are declared separately from ordinary method sets and participate in constraint resolution. An instance is an orphan when neither the class nor an instance-head type is declared in its module. Orphans can make instance discovery and recompilation broader because compilers must account for orphan modules. GHC has overlapping/incoherent instance extensions, with additional rules and risks: distinct program regions may resolve constraints differently under incoherent choices. This offers flexible generic dispatch but makes global instance visibility, consistency, and compilation dependencies central concerns.

Sources: [GHC User's Guide — Instance declarations and resolution](https://downloads.haskell.org/ghc/latest/docs/users_guide/exts/instances.html), [GHC User's Guide — Separate compilation and orphan modules](https://downloads.haskell.org/ghc/latest/docs/users_guide/separate_compilation.html), [GHC User's Guide — Orphan warnings](https://downloads.haskell.org/ghc/latest/docs/users_guide/using-warnings.html).

## 3. Candidate policies

| Candidate | Ownership and lookup policy | Trade-offs |
|---|---|---|
| IC-A — Owner-local explicit implementations | Permit implementations only in the module/package defining the interface or the type; reject all overlapping impl heads. | Strong deterministic authority and upgrade safety; adapters/newtypes needed for foreign integrations. |
| IC-B — Implicit structural satisfaction | Interfaces describe required methods; compatibility is computed at each use, without global implementation records. | Decoupled and convenient consumer-defined interfaces; accidental conformance and interface evolution pressure. |
| IC-C — Explicit unique conformance with guarded retroactivity | Allow explicit implementations in extension modules, enforce a single canonical conformance, and warn or require annotation when both sides are foreign. | Flexible integration and discoverable conformance; needs package-wide conflict checks and robust cross-module metadata. |
| IC-D — Scoped instances | Allow multiple implementations in distinct lexical/module scopes; calls resolve only from an explicit import/instance environment. | Supports local adaptation and alternatives; environment-sensitive behavior complicates inference, caching, and API understanding. |
| IC-E — Overlapping prioritized instances | Permit overlapping generic implementations under explicit specificity/priority rules. | Expressive generic dispatch; resolution, coherence proofs, and dependency evolution become significantly harder. |

## 4. Discriminating experiments

1. Build a three-package graph: upstream type owner, interface owner, and downstream integration. Try adding an upstream conformance after the downstream integration exists; compare compile diagnostics and upgrade behavior.
2. Create two third-party implementations for the same type/interface pair, then test transitive imports, separate compilation, link order, and runtime behavior. Record whether the conflict is rejected statically or selection depends on scope/import order.
3. Add a new interface method and a new default implementation in separate versions. Measure source and binary compatibility and whether previously satisfying types silently change behavior.
4. Compare explicit conformance and structural method satisfaction for generic constraints, overload selection, dynamic dispatch, witness/dictionary generation, and reflection.
5. Test generic/conditional implementations (`T` where `T: P`), specialization, associated types, recursive constraints, and overlap boundaries; verify deterministic resolution independent of module and source order.
6. Measure separate-compilation invalidation and package-index cost when implementation metadata changes, especially for orphan/retroactive instances.
7. Test fallback integration strategies—local wrapper, adapter, explicit import, or scoped instance—for syntax burden, discoverability, and whether they preserve representation and type identity.

## 5. Current result

Implementation ownership, satisfaction style, overlap handling, and lookup scope are distinct choices. Owner-local explicit coherence limits conflicting global claims; implicit structural satisfaction avoids global conformance records; explicit retroactive systems make imported conformance metadata and conflicts visible design concerns; scoped or overlapping instances offer flexibility at a cost in resolution stability. No LLMLang policy is selected. Generic specialization, conformance metadata ABI, and build invalidation require matched experiments before RFC synthesis.

## Public-interface integration (2026-11-24; proposed)

Follow-up: a public operation can have multiple independently verified provider candidates; coherence is a property of selection scope and policy, not necessarily global uniqueness of conformance. Compare explicit provider bindings and structural discovery, orphan/ownership policy, overlapping generic providers, and ambiguous selections. A declared impl or method-shape match is not behavioral evidence. Group interfaces require joint protocol obligations. Existing comparative results are unchanged.

Related: [Public interfaces and verified contract refinement](../../semantic-representation/RT-05/PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md). This is a candidate follow-up; it does not change accepted rules or previously reported evidence.
