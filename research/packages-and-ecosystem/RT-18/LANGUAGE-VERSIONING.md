# LLMLang Language Versioning — Research Design

**Status:** accepted design direction; detailed compatibility and serialization rules remain open.  
**Scope:** composite language versions and the append-only component registry.  
**Related:** [Package System](../RT-12/PACKAGE-SYSTEM.md), [Semantic Compilation Cache](../../toolchain-and-collaboration/RT-11/SEMANTIC-COMPILATION-CACHE.md), [LL-021](../../../PLAN.md#open-design-questions).

## 1. Purpose

A language version identifies the normative language definition used to interpret, validate, compile, test, or verify LLMLang artifacts. It is distinct from the version or identity of the compiler and other tools that process the language.

The language version is a composite, dot-separated sequence. Each coordinate is the version of one language component, in the stable order defined by `language-components.toml`.

## 2. Component registry

The root-level `language-components.toml` file contains only the ordered list of component identifiers. It contains no component versions, compatibility declarations, release metadata, or descriptive prose.

The initial component order is:

1. `syntax`
2. `core_semantics`
3. `type_system`
4. `effects_execution`
5. `modules_packages`

The registry is fixed in ordering but extensible by appending new identifiers.

### 2.1 Append-only invariants

- Existing component identifiers are permanent and immutable.
- Existing entries must never be deleted, reordered, or renamed.
- New components may only be appended to the end.
- An identifier must never be reused for a different component.
- A retired component remains in the registry; retirement does not remove its coordinate.
- Human-readable descriptions may evolve elsewhere, but the identifier and its position are stable.
- Registry changes require review and dedicated validation; ordinary component-version changes do not modify the registry.

The registry is a coordinate definition, not a versioned list of component releases.

## 3. Composite version representation

A language version has one non-negative integer coordinate per component, in registry order. For the initial registry, an example is:

`1.3.2.1.0`

The coordinates respectively identify the versions of syntax, core semantics, type system, effects/execution, and modules/packages.

The component versions evolve independently, but their compatibility is not assumed to be independent. A compatibility relation must be declared or validated; numeric ordering alone does not establish compatibility.

### 3.1 Registry growth and older versions

When a component is appended, it receives a new trailing coordinate. Existing coordinates retain their meaning and position.

A version written before the append may omit newly added trailing coordinates; each omitted trailing coordinate is interpreted as zero. Parsers must reject missing coordinates in the middle, extra coordinates not present in the applicable registry, negative values, non-integers, and ambiguous spellings.

For durable records, the registry snapshot used to interpret the tuple must also be identifiable. The registry file itself remains version-free; its exact content can be identified by a cryptographic digest stored alongside the language version. Compatibility between registry snapshots may be granted only when the append-only invariants are verified and the added coordinates are zero or covered by explicit compatibility evidence.

The exact canonical textual form, digest algorithm, and compatibility declaration format remain open.

## 4. Separate version identities

Keep these identities distinct:

- **LanguageVersion:** the composite versions of normative language components.
- **LanguageComponentRegistryDigest:** digest of the exact ordered component registry used to interpret the tuple. This is derived metadata; it is not stored in the registry file.
- **ToolchainVersion / ToolchainIdentity:** identity of the compiler, verifier, formatter, package manager, and other tools. It must identify result-determining tool builds/components precisely enough for reproducibility.
- **TargetProfile:** target architecture, ABI, runtime and platform constraints where they affect behavior or generated outputs.
- **StdlibVersion:** standard-library identity/version, kept separate from the language component tuple unless later research demonstrates that it is inseparable from a normative language component.

A toolchain upgrade does not automatically imply a language-version change. A language component change does not identify which toolchain build performed an action.

## 5. Cache and package binding

Every cached action result must record at least:

- `language_version`;
- `language_component_registry_digest`;
- `toolchain_identity` (and any independently relevant tool component identities);
- target/profile and configuration inputs where they affect the action.

Include these values in the Action Key whenever they can affect the result. A cache result produced under another language version or registry snapshot is not reusable merely because its numeric tuple appears similar. Reuse requires exact identity or explicit, validated compatibility evidence. A toolchain change that can affect the result likewise requires a different key unless compatibility is established.

Package cache indexes remain optional derived data. These version fields and cache records do not alter semantic package identity.

## 6. Open decisions

- Exact canonical syntax and bounds for each component version coordinate.
- Whether a registry digest is carried in every manifest/cache record or referenced through an immutable language release descriptor.
- Formal compatibility declaration format and the authority that validates it.
- Whether language component versions follow a specific numeric increment policy.
- Exact ToolchainIdentity structure and the role of tool component digests.
- Standard-library compatibility and versioning policy.
- Migration rules for existing packages and cache records that contain a combined language/toolchain version field.

## 7. Current decision boundary

The append-only ordered registry and composite-version direction are accepted design decisions. The initial component identifiers above are the starting registry. This document is research/design material, not yet a normative language specification; implementation must wait until the open serialization and compatibility rules are resolved.

## Public-interface integration (2026-11-24; proposed)

Separate the language/toolchain composite version from public interface lineage/revision, provider binding and package release. A compatible public contract evolution is a relation to the prior immutable revision, not a numerical version comparison or guarantee of cross-toolchain ABI/wire compatibility. Preserve the accepted single-toolchain build boundary; interface labels/major-version policy remain candidate. Exact pinned old operations stay resolvable where retained by policy.

Related: [Public interfaces and verified contract refinement](../../semantic-representation/RT-05/PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md). This is a candidate follow-up; it does not change accepted rules or previously reported evidence.
