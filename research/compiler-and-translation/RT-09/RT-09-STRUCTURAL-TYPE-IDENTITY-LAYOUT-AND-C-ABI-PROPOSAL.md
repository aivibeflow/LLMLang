# RT-09 Proposal — Structural Type Identity, Representation Requirements, Layout, and C ABI

**Status:** Architecture proposal derived from design discussion; not an accepted language specification or validated ABI implementation  
**Research areas:** RT-03 data representation and semantics, RT-04 type system, RT-05 semantic identity, RT-09 compiler/ABI/interoperability  
**Date:** 2026-11-22  
**Related:** [LLMLang Concept](../../language-design/RT-01/LLMLang-CONCEPT.md), [RT-04 type/effect/ownership alternatives](../../language-design/RT-04/RT-04-TYPE-EFFECT-OWNERSHIP-AND-CAPABILITY-ALTERNATIVES.md), [Scenario 70 — type identity and representation](../../language-design/RT-04/RESEARCH-SCENARIO-70-TYPE-ALIASES-NEWTYPE-AND-OPAQUE-ABSTRACTIONS.md), [Scenario 72 — layout and ABI](../RT-13/RESEARCH-SCENARIO-72-SUM-TYPE-LAYOUT-ABI-AND-INTEROPERABILITY.md), [Research Dependency Map](../../RESEARCH-DEPENDENCY-MAP.md)

## 1. Purpose

This proposal records a candidate architecture for LLMLang types and native interoperability. Its central separation is:

`Identity → Type → Layout → Function ABI`

The levels answer different questions:

1. **Identity:** What is the structural data shape?
2. **Type:** What requirements and constraints apply to values having that identity?
3. **Layout:** What concrete in-memory representation satisfies those requirements for a selected target?
4. **Function ABI:** How are values and control transferred across a particular function-call boundary?

The proposal is intentionally not a claim that these decisions have already been validated against all targets or selected as normative language semantics.

## 2. Structural identity

### 2.1 Identity is derived from canonical structure

A structural identity is computed from a canonical, name-independent description of the data shape.

For a product/record-like structure, the canonical description includes at least:

- the kind of aggregate (for example, struct versus union);
- the number of fields;
- field order where order is semantically/representationally significant;
- the structural identity of each field type;
- array extents and other type constructors;
- nested type structure and recursive references;
- any other source-level type constructor that changes the value's structural shape.

Field names, declaration names, aliases, source locations, documentation, and domain meaning are excluded.

`IdentityHash = H(domain_separator, canonical_structural_description)`

Two declarations with the same canonical structure therefore have the same Identity Hash even if their type names and field names differ.

Illustrative declarations:

```rust
struct Point {
    x: i32,
    y: i32
}

struct Coordinates {
    latitude: i32,
    longitude: i32
}
```

If both declarations resolve to the same ordered pair of `i32` fields, they have the same structural identity. The names remain available as declaration metadata and source-level access labels, but do not distinguish the structural identity.

### 2.2 Field names and consumer semantics

Field names are not part of structural identity and must not be used as implicit domain semantics.

A consumer may assign meaning to positions or components through its own contract. For example, a function may require that component 0 represents an x-coordinate and component 1 represents a y-coordinate. That interpretation belongs to the consumer's semantic contract, not to the shared data identity.

The exact source syntax for positional access, declaration-local field labels, and consumer-side semantic bindings remains open. Whatever syntax is chosen, renaming a field label alone must not change Identity Hash.

### 2.3 Structural identity is not nominal foreign identity

Foreign languages may have nominal rules that distinguish declarations even when their field structures match. In particular, imported C declarations must retain enough foreign declaration metadata to preserve C name lookup, tag identity, compatibility rules, and correct binding generation.

This does not require LLMLang's structural Identity Hash to become nominal. Keep separate:

- LLMLang structural identity;
- foreign declaration identity and provenance;
- source-level aliases and names;
- representation requirements and resolved layout.

A binding must not infer C type compatibility solely from equal LLMLang Identity Hash values.

### 2.4 Recursive structures

Canonicalization must support recursive and mutually recursive type graphs without naïve infinite recursive hashing. A deterministic graph-canonicalization or explicitly defined recursive-group encoding is required. The exact algorithm is open and must be tested for declaration-order independence, alpha-renaming, graph isomorphism, and stable serialization.

## 3. Type as identity plus requirements

### 3.1 Type Hash

A Type is an identity extended with canonical requirements that constrain valid representations or uses of values of that type.

`TypeHash = H(domain_separator, IdentityHash, canonical_type_requirements)`

One Identity Hash may therefore be associated with multiple Type Hash values when distinct representation contracts are requested.

Examples of requirements that may participate in Type identity include:

- an explicit representation family or foreign representation requirement, such as a C-compatible representation;
- required minimum or exact alignment, where the language defines the distinction;
- packing constraints;
- representation-affecting field constraints;
- other explicitly declared constraints that change which physical representations are valid.

The canonical requirements must be normalized so that equivalent requirement sets hash identically regardless of declaration order. Conflicting or unsatisfiable requirements must be diagnosed rather than silently weakened.

### 3.2 What does not belong in Type Hash

The following do not belong in structural Identity Hash or Type Hash merely because they describe a use site:

- field and type display names;
- domain meaning such as Point, Vector, UserId, or ProductId;
- consumer-specific semantic interpretations;
- function parameter names;
- the identity of a function that happens to consume the type;
- source paths, formatting, authorship, and provenance.

A consumer's behavioral preconditions, postconditions, units, coordinate interpretation, ownership protocol, and other semantic expectations belong in consumer/function contracts or separate semantic-contract objects. They must not be smuggled into the data type unless a separately specified type-system feature explicitly makes them type constraints.

### 3.3 Requirements versus target rules

A Type records the required contract, not the compiler's answer for one machine.

A target-independent requirement such as C-compatible representation is resolved using a concrete target ABI profile during compilation. The Type Hash commits to the declared representation requirement and its canonical parameters; the target ABI profile is an input to layout resolution.

The precise encoding of ABI-family requirements, profile versioning, and target constraints remains to be specified.

## 4. Layout is a derived compile-time result

### 4.1 Layout Engine

The compiler derives Layout from:

- the resolved Type;
- the target triple and data model;
- the selected ABI profile and its version;
- target/compiler configuration that is documented as layout-relevant.

Layout is not a second source-level type declaration and must not introduce an independent set of requirements that can contradict Type.

The Layout Engine is the single source of truth for layout calculations used by type checking, constant evaluation, code generation, FFI validation, and layout queries.

### 4.2 Layout Descriptor and Layout Hash

A resolved Layout Descriptor may contain:

- total size and alignment;
- each field's byte offset, size, and effective alignment;
- internal and trailing padding;
- array stride;
- union storage size and alignment;
- bit-field allocation details where supported;
- flexible-array-member offset and applicable constraints;
- other target-specific representation facts.

Conceptually:

`LayoutHash = H(domain_separator, TypeHash, TargetABIProfileIdentity, canonical_resolved_layout)`

A Layout Hash identifies one resolved physical layout, not the abstract data shape alone. It is expected to differ when target ABI rules or resolved layout facts differ.

The compiler may compute layouts lazily and cache them. A layout must be available whenever required for code generation, constant evaluation, an explicit layout query, or ABI validation. Lazy evaluation is an implementation strategy, not permission to defer a required diagnostic past compilation.

### 4.3 Requirement satisfaction

The Layout Engine must either produce a layout satisfying every Type requirement or report that the requirements cannot be met for the selected target/profile.

It must not silently:
- reduce requested alignment;
- ignore packing;
- substitute a different representation family;
- alter field order;
- assume a foreign ABI rule that is not supported by the selected profile.

### 4.4 Layout queries

The language may expose compile-time queries such as size, alignment, and field offset. Such queries observe the compiler-derived Layout; they do not make Layout a separately declared source type.

Illustrative syntax only:

```rust
static_assert(sizeof(Point) == 8);
static_assert(alignof(Point) == 4);
static_assert(offset_of(Point, 0) == 0);
static_assert(offset_of(Point, 1) == 4);
```

The exact syntax, constant-evaluation rules, and behavior for opaque/incomplete types remain open.

## 5. Function ABI is a derived call-boundary contract

### 5.1 ABI belongs to the function boundary

A function declaration carries the foreign calling-convention/ABI requirement for that boundary. It does not belong globally to every type used by the function.

Illustrative syntax:

```rust
extern "C" {
    fn process(point: Point);
}
```

Here `"C"` selects the C calling-convention family. The concrete platform ABI profile is resolved from the compilation target and toolchain configuration.

The same structural Type may be passed to functions using different calling conventions without changing its structural identity. The function declarations have different call-boundary contracts.

### 5.2 Function ABI Descriptor

The compiler derives a Function ABI Descriptor from:

- the function signature and relevant function-type properties;
- the declared calling convention;
- the resolved target ABI profile;
- each parameter and result Type;
- each parameter/result Layout;
- target-specific aggregate classification and lowering rules;
- variadic status and other call-boundary attributes where applicable.

The descriptor determines such matters as:

- register classes and register assignment;
- stack placement and alignment;
- indirect/by-reference passing;
- hidden result pointers;
- aggregate splitting/coercion;
- return-value classification;
- variadic calling rules;
- required caller/callee cleanup and other ABI-defined mechanics.

Conceptually:

`FunctionABIHash = H(domain_separator, canonical_function_signature, calling_convention, TargetABIProfileIdentity, resolved_parameter_and_result_abi)`

The hash must identify the resolved call contract, not merely the source spelling of the function signature.

If calling convention changes callable compatibility, it must participate in the identity/compatibility rules for function types. The exact relationship between function-type identity and a target-resolved Function ABI Hash remains to be formalized.

### 5.3 Why Layout is insufficient

Equal size, alignment, and field offsets do not imply equal function-call ABI. Different ABIs can classify and pass the same aggregate differently. Therefore, matching Layout Hash values alone cannot establish that two functions can call one another safely.

## 6. Compile-time pipeline and source-level model

At source level, developers declare and use Types and functions. Layout and Function ABI are compiler-derived artifacts.

```text
Source declarations
       |
       v
Structural identity resolution
       |
       v
Type construction
(Identity + canonical requirements)
       |
       v
Target and ABI profile selection
       |
       +----------------------+
       |                      |
       v                      v
Layout resolution       Function ABI lowering
       |                      |
       +-----------+----------+
                   |
                   v
             Code generation
```

The compiler may resolve these artifacts lazily and cache them. They are not alternate source-level types and must not be manually duplicated by each backend.

| Entity | Primary responsibility | Source-level declaration? | Target-dependent? |
|---|---|---:|---:|
| Identity | Canonical structural data identity | Derived from type declaration | No, except where the language's primitive/type constructors explicitly depend on target |
| Type | Identity plus canonical representation requirements | Yes / resolved by type system | Requirements may be target-independent; satisfiability is target-dependent |
| Layout | Concrete size, alignment, offsets, padding, and storage | No; compiler-derived | Yes |
| Function ABI | Concrete call-boundary passing and return rules | Function declaration supplies the ABI requirement; descriptor is derived | Yes |

## 7. C interoperability requirements

The goal is to support C bindings without requiring developers to manually reproduce C layout and call rules.

### 7.1 C-compatible aggregates

The candidate C representation mode must cover the C aggregate model, including:

- `struct` and `union`;
- nested aggregates;
- arrays and pointers;
- incomplete/forward-declared aggregate types;
- enums and typedef names;
- function pointers;
- anonymous struct/union members where supported by the selected C language version;
- bit-fields;
- flexible array members;
- implementation-defined and compiler-specific attributes where explicitly supported.

A claim of exact C compatibility must be scoped to a named target ABI profile, C language mode, and relevant compiler ABI behavior. C does not define one universal cross-platform layout for every implementation-defined feature.

### 7.2 Alignment, packing, and bit-fields

The implementation must model natural alignment, explicit alignment, packing, and target-specific bit-field allocation rules. Bit-field order, allocation units, zero-width fields, and interactions with packing are ABI-sensitive and cannot be assumed portable.

Packed fields may be unaligned. The language/backend must define safe load/store lowering and must not silently generate target-invalid accesses.

### 7.3 C declaration identity and metadata

C import must preserve foreign declaration identity and metadata independently of LLMLang structural identity. This includes C tag names, typedef names, source declaration relationships, field names for binding generation, qualifiers, attributes, and provenance as needed.

Two C declarations with equal LLMLang structural identity are not automatically interchangeable as C types. The importer must enforce the applicable C compatibility rules and preserve the exact foreign declaration binding.

### 7.4 Import pipeline

A practical importer may use Clang AST/LibTooling or another conforming frontend to parse headers and obtain target-specific declaration information. That tool is an import/validation mechanism, not the definition of LLMLang type semantics.

The importer should produce:
- LLMLang structural identity and Type requirements;
- preserved foreign declaration identity and source metadata;
- target/profile-scoped layout expectations;
- external function declarations with calling-convention requirements;
- diagnostics for unsupported extensions or ambiguous/incomplete ABI information.

The generated bindings must be validated against the actual C toolchain/profile used for the library. Layout probes and call probes should compare size, alignment, offsets, aggregate pass/return behavior, and relevant edge cases.

## 8. Hash and identity layers

The proposed hash hierarchy is:

| Hash | Commits to | Does not establish |
|---|---|---|
| Identity Hash | Canonical structural data shape, excluding names and consumer semantics | ABI compatibility or behavioral meaning |
| Type Hash | Identity plus canonical type/representation requirements | A concrete target layout or function call sequence |
| Layout Hash | Type plus target ABI profile and resolved physical layout | Function argument/return classification |
| Function ABI Hash | Function signature, calling convention, target ABI profile, and resolved call-boundary rules | Behavioral correctness of the function implementation |

Use domain separation and canonical encodings for each hash purpose. Hash collisions must be handled by verifying the canonical descriptors; a digest is not a mathematical proof of uniqueness. Hash algorithm, serialization, schema versioning, recursive graph canonicalization, and migration policy remain open.

## 9. Consumer semantics remain separate

A data structure does not acquire domain meaning merely from its field labels or declaration name.

A function or other consumer may specify semantic expectations such as:
- component 0 is an x-coordinate and component 1 is a y-coordinate;
- values use a particular unit or coordinate system;
- a byte sequence follows a particular protocol;
- a handle obeys a particular ownership/lifetime protocol;
- input values satisfy preconditions and output values satisfy postconditions.

These expectations belong to the consumer's contract or a separately identified semantic contract. They can refer to the Type but must not alter Identity Hash or Type Hash unless a requirement is explicitly part of the type's admissibility/representation contract.

This keeps structural reuse independent from domain interpretation and prevents accidental nominal types from being created solely to encode consumer vocabulary.

## 10. Illustrative end-to-end example

C source:

```c
#include <stdint.h>

typedef struct Point {
    int32_t x;
    int32_t y;
} Point;

void process(Point point);
```

Conceptual LLMLang binding:

```rust
@repr(C)
struct Point {
    i32,
    i32
}

extern "C" {
    fn process(point: Point);
}
```

The compiler then:

1. Computes the structural Identity Hash from the ordered pair of `i32` fields; `Point`, `x`, and `y` are not hash inputs.
2. Constructs the Type and Type Hash from that identity plus the C representation requirement.
3. Resolves the target's C ABI profile and derives the Layout Descriptor and Layout Hash.
4. Derives the function's ABI descriptor using the external declaration's C calling convention, the target ABI profile, the parameter Type/Layout, and the platform's aggregate argument classification.
5. Rejects compilation if the requested representation or call contract cannot be satisfied.
6. Retains C declaration metadata so that foreign binding compatibility is not inferred from structural hash equality alone.

The example syntax is illustrative; it does not select final LLMLang grammar.

## 11. Candidate architecture rules

The proposal recommends the following rules for further validation:

1. Structural identity is content-derived from a canonical description of data shape.
2. Field names, type names, aliases, source locations, and semantic purpose do not participate in structural Identity Hash.
3. Type is an extension of structural identity with canonical representation/admissibility requirements; its hash is derived from Identity Hash plus those requirements.
4. Consumer-specific semantic meaning and behavioral contracts are separate from data identity and Type unless explicitly elevated to a type requirement.
5. Layout is a target-resolved compiler artifact derived from Type and a versioned ABI profile.
6. Function ABI is a target-resolved compiler artifact derived from a function declaration, calling convention, argument/result Types and Layouts, and ABI profile.
7. Source code operates on Types and function declarations; Layout and Function ABI are computed and cached by the compiler when required.
8. The Layout Engine is the single authority for physical layout across code generation, constant evaluation, FFI, and compile-time queries.
9. ABI requirements must be checked exactly; unsupported or unsatisfiable requirements fail closed.
10. C foreign declaration identity and metadata are preserved independently of LLMLang structural identity.
11. C compatibility is target/profile-specific; no universal C layout or calling sequence is assumed.
12. C bindings cover aggregates and the associated pointer, array, enum, function-pointer, and call-boundary rules—not merely struct syntax.

## 12. Open research and validation work

Before this proposal can become normative, investigate and validate:

- canonical encoding and graph canonicalization for recursive structural identities;
- exact distinction between structural and nominal identity, including C compatibility rules;
- which representation requirements belong in Type Hash and how they compose;
- whether ABI-family selectors and target profile versions are Type requirements, function-boundary requirements, or both;
- exact alignment/packing semantics and conflicts;
- C struct/union/enum/bit-field/flexible-array layout across selected targets;
- aggregate argument and return classification for SysV AMD64, Windows x64, AArch64 platform ABIs, and other prioritized targets;
- function pointers, variadic calls, callbacks, and cross-language unwinding/error boundaries;
- interaction with generics, opaque/incomplete types, zero-sized types, and compiler optimizations;
- whether and how imported C declarations map onto structurally identical LLMLang Types without erasing foreign nominal compatibility;
- differential validation against Clang and platform C compilers, including generated layout and call probes;
- hash stability, versioning, collision handling, and cache invalidation.

No implementation should claim general C compatibility until the supported C language modes, target triples, ABI profiles, compiler versions, and tested feature subset are explicitly listed.

## Public-interface integration (2026-11-24; proposed)

A public interface's stable name and behavioral contract are not structural Identity, TypeHash, LayoutHash or Function ABI Hash. A change may be contract-compatible but ABI-incompatible, or ABI-compatible but behaviorally incompatible. A source-level public operation can select an exact provider with a separately verified foreign adapter and target-specific ABI/export mapping. Preserve layout engine authority; test changed layout, call convention, error representation, and proof claims under a pinned ABI profile.

Related: [Public interfaces and verified contract refinement](../../semantic-representation/RT-05/PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md). This is a candidate follow-up; it does not change accepted rules or previously reported evidence.

## RT-36 follow-up: explicit assumptions (proposed)

Exact ABI and layout compatibility are necessary but not sufficient to establish foreign behavior. Retain explicit provider and correspondence premises for conditional proofs. See [RT-36 — Formal Verification Assumptions, Trust Boundaries and Conditional Proof Management](../../formal-verification/RT-36/RT-36-FORMAL-VERIFICATION-ASSUMPTIONS-AND-TRUST.md). This cross-reference does not change adopted rules or previously reported evidence.
