# Structure Inheritance, Composition, and Template Specialization

**Status:** User-confirmed discussion synthesis; candidate design, not yet normative  
**Date:** 2026-11-22  
**Primary research area:** RT-03 — Core language semantics  
**Related areas:** RT-04 (types, ownership, and borrowing), RT-06 (dependency semantics), RT-07/08 (formal verification), RT-20 (verified change lifecycle)

> This document records decisions confirmed in the LLMLang structure/class design discussion. It is a research synthesis, not a normative specification. It complements the structure-contract and invariant synthesis proposed separately in [PR #226](https://github.com/aivibeflow/LLMLang/pull/226), which covers invariant ownership, compatibility, dependency analysis, deferred checking, and atomic commit. Unresolved points are listed explicitly.

## 1. Design principles

LLMLang structures are governed by explicit types, ownership/borrowing rules, contracts, and invariants. C++ access modifiers are not used as the mechanism for preserving invariants: mutable access is governed by borrowing and contract verification.

The model distinguishes:
- inheritance, which composes a child structure with the structural and invariant obligations of its parents;
- composition, which embeds independently owned structure values as fields;
- template specialization, which provides explicitly declared structure/function variants for concrete type arguments.

The language does not perform type inference and does not support metaprogramming. Template parameters and specialization arguments are explicit. Templates do not provide compile-time evaluation, arbitrary code generation, or automatic deduction of missing type arguments.

## 2. Structure inheritance

### 2.1 Parent guarantees

- A child inherits all parent invariants and contract guarantees.
- A child may add stricter invariants and constraints.
- A child may not weaken, remove, or override parent guarantees.
- Compatibility among inherited and newly declared invariants is checked statically under the global compatibility policy.
- The inheritance graph must be acyclic; cycles are rejected statically.
- Any structure may be inherited from; no sealed/final restriction has been selected.

Multiple inheritance is supported. Parent contracts remain independently identifiable and their invariants remain independently declared, even when logically equivalent.

### 2.2 Fields

- Inherited fields retain their original type and semantics.
- A child cannot redefine an inherited field with a different type or semantics.
- A child may add new fields.
- If multiple parents declare fields with the same name, those fields remain distinct; they are not merged, even if their types and semantics match.
- A duplicated field name is accessed with explicit parent qualification, such as A.id or B.id.
- A field whose name is unique across the inherited fields may be accessed without qualification.
- Local aliases for inherited fields remain an open design question; no support decision has been made.
- Multiple-inheritance field identity and object representation follow the C/C++ inheritance model: distinct parent subobjects and their fields are not merged. Parent declaration order determines parent initialization order. Exact offsets, padding, and ABI guarantees remain a separate specification question.

### 2.3 Initialization and destruction

- The child initializer is responsible for initializing every inherited and child-owned field.
- Parent initialization is explicit; there is no implicit default initialization of parent parts.
- A child initializer may explicitly invoke parent initializers and reconcile their requirements.
- Parent subobjects are initialized in the order in which the parents are declared, regardless of the order in which their initializers are written in the child initializer; the analyzer checks this order.
- Child-owned fields are initialized after parent subobjects, following their declaration order.
- If parent initializers have incompatible requirements, the child may explicitly reconcile them only when the reconciliation is statically provable and the resulting state satisfies every parent and child invariant.
- Destruction follows reverse initialization order: the child part is destroyed first, followed by parent parts in reverse order of initialization.
- Each parent is responsible for lifecycle and resource cleanup of its own fields.

### 2.4 Invariants across parent parts

A child invariant may refer to fields from multiple parents and fields introduced by the child. It may require coordinated updates across those fields. The compiler analyzes dependencies and verifies the resulting obligations statically, subject to the selected per-invariant check policy and the global invariant model.

Inherited duplicate invariant declarations remain independent. They are not merged merely because equivalence is established.

## 3. Structure composition

Composition embeds another structure as a field and is distinct from inheritance.

- A nested structure retains its own identity, ownership, invariants, contract, and lifecycle.
- The outer structure does not acquire the nested structure's fields as inherited fields.
- Nested invariants remain mandatory and are checked when the nested value may be affected.
- The outer structure may add invariants that relate its own fields to fields of nested components.
- A nested field may be mutated directly through the outer value when ordinary ownership and borrowing rules permit it; mutation does not have to pass through an outer-structure method.
- An outer contract may explicitly include component contract obligations. This does not replace or weaken the component's own invariants.
- ImplHash(component) identifies an implementation associated with the component; ImplHash(outer) identifies one associated with the outer structure. Composition does not implicitly delegate implementation ownership.
- An outer operation may invoke an implementation for a nested component only when the outer operation's contract requires or permits that behavior.
- Cyclic by-value composition is forbidden because it would imply an infinitely sized value. Cycles through references or weak ownership are governed by the ownership, lifetime, and borrowing rules.

## 4. Function implementations and structure types

Structure inheritance does not imply implicit subtype conversion or implicit type conversion.

- Function argument types match exactly.
- A function accepting a parent structure does not thereby accept a child structure.
- Distinct specializations of the same template are distinct, incompatible types unless an explicit LLMLang conversion mechanism is used.
- Inheritance does not itself create an implicit conversion between parent and child types.
- Conversions are permitted only through explicitly defined LLMLang mechanisms; no implicit conversion is inferred from structural similarity, inheritance, or shared template origin.
- When behavior is intended for multiple concrete structure types, a template function may be used.
- Template function specialization is separate for each explicitly supplied concrete type.
- Function implementations and contracts remain independent entities linked through ImplHash; structural inheritance alone does not implicitly inherit or override an implementation.
- A concrete ImplHash implementation may apply to a child structure when the child satisfies the implementation's contract. This does not make the child type interchangeable with the parent type.

These rules deliberately separate structural inheritance from type assignability and implementation selection.

## 5. Copy and move

### 5.1 Copy

Copyability is inferred from the complete structure:
- all parent parts;
- all child-owned fields;
- nested components;
- applicable invariants and ownership rules.

If any parent part, field, or nested component is non-copyable, the complete structure is non-copyable. A developer may explicitly prohibit copying even when all parts are otherwise copyable. A parent's prohibition propagates to descendants and cannot be lifted by a child.

Reference fields follow Rust-like capability semantics:
- An immutable reference is copyable. Copying it copies the reference, not the referred-to value, and preserves the same lifetime constraints.
- A mutable exclusive reference is not copyable; moving it transfers the exclusive borrow.
- A structure containing references is copyable when every field is copyable and the structure's other Copy conditions are satisfied. The mere presence of a reference does not prohibit Copy.
- Shared-ownership handles analogous to `Rc`/`Arc` are not implicitly copied. Explicit cloning creates another strong owner and updates the ownership count; it does not copy the underlying object.

### 5.2 Move

Move is an ownership transfer, not a user-defined move-constructor mechanism. Moving an outer structure transfers its owned fields and nested components as a whole. References and borrows retain their own lifetime and ownership constraints. The moved-from binding is unavailable unless the type is copyable under the language's Copy rules.

## 6. Templates

### 6.1 Template structures and functions

- Template structures are supported.
- Template functions are supported.
- Each concrete set of explicitly supplied template arguments identifies a separate specialization.
- An ordinary structure may inherit from a concrete template specialization, which is then treated as a concrete parent structure under the ordinary inheritance rules.
- Template parameters are explicitly supplied. LLMLang does not infer missing type arguments.
- Templates are not a metaprogramming facility: they do not perform arbitrary compile-time computation or generate code through compile-time execution.

### 6.2 Constraints on template parameters

Template parameters may declare explicit constraints describing the properties required of the supplied type. Invariant and contract verification uses those declared constraints and the concrete specialization. The candidate model provisionally supports three constraint categories:
- structural constraints, describing required fields and their types;
- contract constraints, requiring the parameter type to satisfy a specified contract through the ordinary contract/`ImplHash` mechanism;
- invariant constraints, requiring specified invariants to be established for the parameter type.

The three categories are accepted provisionally. Their exact syntax, formal semantics, interaction, and proof/checking rules are intentionally deferred to detailed design during implementation.

For example, if a template invariant requires an ordering operation, the template must explicitly constrain its parameter to provide the required operation and semantics. The checker does not assume that an arbitrary type supports that operation.

A child of a template structure may add constraints to the specialization parameters only when those constraints are compatible with the parent template's contracts and invariants. Compatibility is checked statically.

### 6.3 Template and specialization contracts

Contracts are associated with template structures and their specializations using the same contract and `ImplHash` model as for ordinary structures; no separate template-only contract mechanism is introduced.

- A contract declared for a template structure applies to every specialization of that template.
- A specialization creates a new concrete type and may therefore have additional contracts of its own.
- A specialization-specific contract supplements the template-level contract; the specialization must satisfy both.
- A specialization may not weaken, remove, cancel, or violate any requirement or guarantee of the template-level contract.
- Compatibility is checked statically.

### 6.4 Full and partial specialization

Both full and partial specialization are supported, subject to these restrictions:

- Specialization declarations are explicit.
- A specialization does not rely on type inference or deduction of omitted arguments.
- A specialization preserves every invariant and contract guarantee of the original template.
- A specialization may add stricter constraints only when they are compatible with the original template contract.
- Specialization is a way to declare a distinct implementation for explicitly identified type patterns; it is not compile-time metaprogramming.

Specialization identity and selection follow the same hash-based rules as function implementations associated through `ImplHash`. A specialization is selected by its explicitly identified hash; the compiler does not rank partial specializations by pattern specificity or choose the closest match. Distinct hashes identify distinct specializations. Duplicate declarations are permitted only when their declarations match completely; declarations sharing a hash but differing in content are a conflict. Consequently, overlapping type patterns do not create a specialization-selection ambiguity: the explicit specialization hash determines the selected variant.

## 7. Confirmed decisions

| Topic | Confirmed direction |
|---|---|
| Access control | Invariants are protected by contracts and verification, not C++-style access modifiers |
| Parent invariants | Automatically inherited; children may strengthen but not weaken guarantees |
| Multiple inheritance | Supported; parent obligations remain independently identifiable |
| Field redefinition | Inherited fields cannot be redefined with different type or semantics |
| Duplicate parent fields | Remain distinct; explicit qualification resolves name collisions |
| Object representation | Multiple-inheritance field identity and parent-subobject model follow C/C++ semantics; exact ABI/layout guarantees remain open |
| Initialization | Child initializes all fields; parent initialization is explicit; parents initialize in declaration order, then child fields in declaration order |
| Destruction | Reverse initialization order, child part first |
| Cross-parent invariants | May relate fields from multiple parent parts and child fields |
| Composition | Nested values retain independent identity, ownership, invariants, and lifecycle |
| Component mutation | Direct mutation is permitted subject to borrowing and all affected invariants |
| Implementation association | ImplHash identifies the target structure; composition does not imply delegation |
| Function argument types | Exact type matching; inheritance does not imply implicit argument compatibility |
| Type conversions | Only explicitly defined LLMLang conversions; no implicit conversion from inheritance or shared template origin |
| Template functions | Separate specialization for each explicitly supplied concrete type |
| Template structures | Supported with separate specializations for explicit concrete type arguments |
| Template parameter constraints | Structural, contract, and invariant constraints provisionally supported; details deferred to implementation design |
| Template contracts | Template-level contract applies to every specialization; specialization contracts may only strengthen it |
| Specialization | Full and partial specialization supported |
| Specialization contracts | Must preserve all original template guarantees; may add compatible stricter constraints |
| Specialization identity and selection | Hash-based, following the same rules as function `ImplHash`; no automatic specificity ranking |
| Duplicate specializations | Allowed only for completely identical declarations; same hash with differing declarations is a conflict |
| Type inference | Not supported |
| Metaprogramming | Not supported |
| Copy | Inferred from all parent parts and fields; immutable references are Copy, mutable exclusive references are not; shared-ownership handles require explicit cloning; explicit prohibition propagates |
| Move | Ownership transfer of the complete owned value |

## 8. Open questions and boundaries

The discussion has not yet selected:
- whether child-local aliases for inherited fields are supported;
- the concrete syntax and formal semantics for template constraints and specialization declarations;
- the exact proof calculus for compatibility and constraint satisfaction;
- the exact set and semantics of explicit conversion mechanisms;
- the ABI/layout consequences of multiple inheritance and composition.

These are not to be inferred from C++ or another language. They require explicit LLMLang decisions and consistency review against RT-03/RT-04 and the invariant model.
