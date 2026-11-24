# Research Scenario 134 — Wire Schema Evolution Across Real Interchange Models

**Status:** Comparative standards analysis completed; no LLMLang wire format, schema identity, or compatibility policy selected  
**Research areas:** RT-03 value/presence semantics; RT-04 data and sum types; RT-05 semantic/interface identity; RT-13 serialization and interoperability  
**Updated:** 2026-11-20  
**Depends on:** Scenarios 109–111  
**Method:** Source-based comparison of official format documentation, mapped against existing finite JSON fixtures. No production serializer, schema registry, or LLMLang compiler was implemented or benchmarked.

> **Applicability decision (2026-11-20):** LLMLang components are immutable/read-only, and compatibility is required only within a build performed by one coherent toolchain version. The toolchain statically checks caller arguments against the callee's callable prototype. The current architecture does not require cross-version wire compatibility, schema negotiation, or persisted-message migration. See [Architecture Decision — Immutable Components and Single-Version Toolchain Compatibility](../../../draft/ARCHITECTURE-DECISIONS.md). This report is retained as prior-art/reference material, not an active LLMLang implementation requirement. Do not start its proposed Protobuf/Avro/CBOR runtime conformance matrix unless a reconsideration trigger in the decision is met. This does not resolve behavioral Contract refinement or future external/persistent data boundaries.

## 1. Research question

What does “schema compatible” mean across real wire-format designs, and which compatibility, preservation, migration, and identity properties must be evaluated independently before LLMLang can define an evolution policy?

Scenarios 109–111 already contain passing bounded JSON models. This study does not repeat them. It addresses their open follow-ups: real format semantics, rename/type evolution, schema metadata, unknown-value relay, canonical encoding, and the relationship between schema fingerprints and semantic identity.

## 2. Scope and evidence boundaries

Official documentation inspected:

- Protocol Buffers: proto3/editions field presence, message evolution, enum behavior, encoding order, and serialization canonicality.
- Apache Avro: writer/reader schema resolution, defaults, aliases, type promotion, enum defaults, Parsing Canonical Form, and schema fingerprints.
- CBOR: generic data model, unknown tags/simple values, validity versus protocol semantics, deterministic encoding, and evolution guidance in RFC 8949.

Repository baseline:

- Scenario 109: absent/null/value representation and error separation.
- Scenario 110: a 16-case JSON producer/consumer/default/unknown-field cross-product.
- Scenario 111: reject/fallback/opaque preservation for an unknown JSON sum case.
- The draft glossary's distinctions among ContractHash, OpHash, ImplHash, CCHash, and CandidateSetHash.

This is an analytical standards comparison. No actual Protobuf, Avro, or CBOR runtime was executed. Claims about a format are limited to the cited documentation; no claim is made that every implementation/version/language binding behaves identically where the source itself documents variation.

## 3. Main finding: compatibility is a vector, not a Boolean

A single compatible=true/false flag hides materially different questions. At minimum, an evolution review must distinguish:

1. **Wire decodability:** can the bytes be parsed under the reader's format/schema?
2. **Value preservation:** are recognized values and distinctions preserved?
3. **Semantic interpretation:** does the reader assign the intended meaning?
4. **Unknown-value preservation:** can an older intermediary retain and forward information it cannot interpret?
5. **Round-trip preservation:** does decode/re-encode retain the original data model, ordering, multiplicity, or exact bytes?
6. **Source/API compatibility:** do generated source types and application code still compile and behave as expected?
7. **ABI/layout compatibility:** do in-memory layouts, calling conventions, or foreign interfaces remain compatible?
8. **Canonical identity:** can independently produced encodings be compared or hashed under a precisely defined equivalence relation?
9. **Migration safety:** can stored data be moved between versions without silent loss, ambiguity, or non-idempotent transformations?

These dimensions can disagree. A change may be binary wire-readable but lose information through a JSON bridge; parse successfully but change meaning because a reader default changed; preserve unknown fields but not their original order; or be deterministic within one build without being canonical across builds.

Compatibility must therefore be reported directionally and by dimension, not collapsed into a single version-to-version label.

## 4. Format comparison

### 4.1 Protocol Buffers

**Field identity and deletion.** Binary wire fields are identified by field numbers, not source names. A field number must not be changed or reused. The official proto3 guide recommends reserving both deleted field numbers and names: number reuse can reinterpret old wire data, while name reuse can affect JSON and TextFormat. This is a stronger lifecycle requirement than Scenario 110, which only adds a new JSON key.

**Presence.** Protobuf distinguishes implicit from explicit presence. Under implicit presence, default-valued scalar fields are omitted from serialization; explicit presence records whether the field was set. A wire stream contains present tag/value pairs, not a separate record of absent fields. Duplicate singular optional values and multiple oneof alternatives follow “last one wins” in the generated API. Field absence, explicit default, and duplicate input behavior cannot safely be inferred from the host-language type alone.

**Unknown values.** Unknown enum behavior differs between open and closed enums and can vary by syntax/edition and generated-language implementation. Closed repeated enums can move unknown values into the unknown-field set and re-emit them after known values, changing their original list position. Unknown fields help forward/backward compatibility, but bridges through JSON or field-by-field reconstruction can discard them.

**Serialization and hashing.** Protobuf explicitly warns that serialization is not canonical. Deterministic serialization is not a stable canonical representation across binaries/builds. Unknown fields make generic canonicalization particularly difficult because a parser cannot always know whether length-delimited unknown bytes should be interpreted recursively as a message or as opaque bytes. Hashing raw serialized bytes is therefore not a sound general-purpose schema/message identity strategy.

**Implication:** Protobuf separates stable numeric wire identity, language-specific API representation, unknown-field retention, and byte serialization. LLMLang must not assume these are one identity boundary.

### 4.2 Apache Avro

**Writer and reader schemas.** Avro binary data omits field names and type tags needed for independent interpretation. The writer schema must be available to the reader. Evolution is defined by resolving a writer schema against a reader schema, not by treating the payload as self-describing.

**Directional resolution.** The reader and writer roles matter. Record fields are matched by name; writer-only fields can be ignored by the reader; reader-only fields require a reader default or resolution fails. Supported promotions include int→long/float/double, long→float/double, float→double, and string↔bytes. Enum symbols unknown to the reader use the reader's enum default if defined, otherwise resolution fails. These are explicit rules, not generic claims that adding fields or widening types is always safe.

**Defaults and aliases.** A record-field default is used when reading data that lacks the field; it does not make the field optional when writing. Aliases can map an old writer name to a new reader name. Defaults and aliases therefore affect evolution behavior, not just parser shape.

**Parsing Canonical Form (PCF).** Avro defines a canonical form for identifying schemas that are the same for parsing. The transform strips metadata such as doc and aliases, and keeps only parsing-relevant attributes. Fingerprints can identify that parsing form and support caches or schema lookup. This is deliberately narrower than a complete identity for all evolution behavior: aliases and defaults can change reader resolution even though PCF strips them. A PCF fingerprint must not be treated as a complete hash of the reader's migration/compatibility policy.

**Implication:** Avro distinguishes writer schema identity, reader resolution behavior, and a parsing fingerprint. A schema identifier sufficient to decode old bytes is not automatically sufficient to identify the compatibility policy used to interpret them.

### 4.3 CBOR

**Generic data model and extensibility.** CBOR is designed for extensibility without mandatory version negotiation. Generic encoders/decoders can carry well-formed simple values and tags unknown to the implementation. RFC 8949 describes forwarding unknown tags/simple values to the application with an explicit indication that they are unrecognized; rejecting every new registered extension can cause protocol ossification.

**Validity versus application semantics.** A CBOR item can be well-formed but invalid under generic-data-model rules, or valid generically but invalid under a particular tag or application protocol. A forwarding layer that does not interpret a semantic layer cannot detect all of its invalidity and must preserve/forward data as specified by the layered protocol. This supports separating a generic opaque representation from a validated domain value.

**Deterministic encoding.** RFC 8949 specifies core deterministic encoding requirements, including preferred shortest encodings, no indefinite-length items, and deterministic map-key ordering. It also requires protocol-specific decisions where multiple representations could be semantically equivalent (for example, tagged versus untagged values or integer versus floating-point forms). Deterministic bytes are not automatically a universal semantic canonical form; the protocol's data model and equivalence rules still matter.

**Implication:** CBOR demonstrates an extensible generic transport model with explicit unknown values, but the application protocol must still define what is valid, meaningful, and safe to execute.

## 5. Cross-format comparison

| Concern | Protobuf | Avro | CBOR |
|---|---|---|---|
| Schema available in payload? | Binary fields are tag-numbered; schema/code defines meaning | Writer schema must be available separately | Basic data model is self-describing; application schema may remain external |
| Field identity | Numeric field number | Field name resolved against writer/reader schemas | Protocol-defined map keys/tags |
| Unknown fields/values | Unknown fields retained in binary APIs, with caveats; open/closed enum behavior varies | Writer-only record fields ignored by reader; unknown enum symbol can map to reader default or error | Generic unknown tags/simple values can be surfaced and forwarded |
| Defaults | Implicit scalar defaults affect presence/serialization; explicit presence is distinct | Reader defaults fill fields absent from writer data; do not make writer field optional | No schema-level default rule in the generic format |
| Rename | Binary field number can remain stable; JSON/TextFormat names add risk | Aliases can map writer name to reader name | Depends on protocol key/tag design |
| Type evolution | Wire-type compatibility rules; semantic/API changes still matter | Explicit reader/writer promotion table | Generic representation may decode; application type constraints decide meaning |
| Unknown enum/case | Open/closed enum and runtime/language behavior matter | Reader enum default or resolution error | Unknown tag/simple value can be carried generically |
| Canonical bytes | Not guaranteed; deterministic is not canonical | PCF and schema fingerprints are defined | Core deterministic encoding exists; application equivalence still must be specified |
| Hashing implication | Do not hash generic serialized bytes as stable message identity | PCF fingerprint is parsing identity, not all evolution metadata | Hashing requires a specified protocol data model and deterministic profile |

The formats are not interchangeable. Protobuf is a tagged field stream with generated APIs; Avro is schema-directed binary encoding with writer/reader resolution; CBOR is a generic data model whose application protocol supplies additional semantics.

## 6. Schema identity and LLMLang hash boundaries

The comparison exposes at least four distinct candidate identities. These are analytical distinctions, not new accepted LLMLang hash definitions.

| Candidate identity | What it would identify | What it must not be confused with |
|---|---|---|
| Source schema identity | Exact schema source/document, including comments, aliases, defaults, names, and authoring metadata | Wire equivalence or reader compatibility |
| Parsing/wire-shape fingerprint | The subset of schema information needed to parse or interpret a specific wire representation | Migration policy, source API, or all reader defaults/aliases |
| Evolution-policy identity | Reader/writer compatibility rules, defaults, aliases, unknown-field/variant policy, and migration behavior | The bytes of one payload or a parser-only fingerprint |
| Wire contract identity | Observable interchange behavior: data model, encoding profile, presence/null rules, version negotiation, unknown-value handling, and canonicalization requirements | Implementation artifact identity or conformance evidence |

The Avro PCF example is a concrete warning: a fingerprint may intentionally omit aliases and defaults, while those attributes still influence resolution. The Protobuf example is a separate warning: even deterministic serialization does not establish canonical bytes across binaries.

The draft glossary already distinguishes ContractHash, OpHash, ImplHash, CCHash, and optional CandidateSetHash. Any future wire/schema identity must be typed and domain-separated rather than overloaded onto one of these names. If a wire contract is externally observable behavior, its requirements may contribute to an operation contract; the implementation's particular codec algorithm belongs to implementation identity only to the extent that it is not independently observable. The exact boundary requires the broader semantic identity study and is not decided here.

Also distinguish:
- a schema's content fingerprint;
- a registry's opaque lookup/version identifier;
- a compatibility verdict for a particular writer/reader pair;
- evidence that a migration preserves required behavior.

None implies the others. A registry ID is a locator, not a proof of compatibility. A content hash is not an authorization or trust statement. A compatibility result is scoped to exact schema versions, encoding, policy, and tool/runtime versions.

## 7. Expanded discriminating corpus

These cases extend rather than replace Scenarios 109–111. They are implementation-ready research discriminators; they were not executed against the real format runtimes in this study.

| ID | Evolution case | Required observations |
|---|---|---|
| WIRE-001 | Add a required field with no default | Writer→reader directions and missing-field behavior are reported separately |
| WIRE-002 | Add a field with a reader default, then change that default | Old payload meaning changes are detected; default is not mistaken for a wire value |
| WIRE-003 | Rename a field with and without an alias | Binary, schema-resolution, JSON, and generated API outcomes are separated |
| WIRE-004 | Delete a field, then attempt to reuse its numeric/name identity | Reuse is rejected or shown to reinterpret old payloads; tombstone/reservation is tested |
| WIRE-005 | Widen/narrow numeric types at boundary values | Overflow, precision loss, and per-format promotion/rejection are explicit |
| WIRE-006 | Change bytes/string or logical type metadata | Wire readability is separated from application semantic equivalence |
| WIRE-007 | Add/remove/reorder oneof or union alternatives | Ambiguous/multiple values, first-match behavior, and last-wins rules are tested |
| WIRE-008 | Add enum case; old consumer reads and relays it | Unknown numeric/symbolic case preservation, fallback, and ordering are checked |
| WIRE-009 | Remove enum case and reuse its numeric/symbolic value | Historical payload reinterpretation is detected |
| WIRE-010 | Round-trip through binary→JSON→binary | Unknown fields, duplicate values, explicit presence, and unknown variants are checked for loss |
| WIRE-011 | Nested unknown field/variant inside list/map/union | Opaque relay preserves semantic structure and position/multiplicity where required |
| WIRE-012 | Duplicate map/object keys or repeated singular fields | Parser validity and protocol-specific duplicate policy are explicit |
| WIRE-013 | Canonical/deterministic encoding under reordered map fields | Equivalent values produce identical bytes only under a named canonical profile |
| WIRE-014 | Unknown extension/tag with application-invalid payload | Generic relay and semantic consumer have distinct outcomes |
| WIRE-015 | Alias/default changes with unchanged parsing fingerprint | Parsing identity and evolution-policy identity are shown to differ |
| WIRE-016 | Writer/reader compatibility across three versions | Pairwise forward/backward/transitive compatibility is tested; no transitivity is assumed |
| WIRE-017 | Migration chain v1→v2→v3 versus direct v1→v3 | Idempotence, reversibility, information loss, and path dependence are measured |
| WIRE-018 | Sign/hash a message with unknown fields or alternate valid encodings | Signature/hash validity is bound to a declared canonical data model, not arbitrary serializer output |
| WIRE-019 | Reuse cached codec/validator after schema metadata change | Cache key commits to every behaviorally relevant schema/policy input |
| WIRE-020 | Registry ID reused/missing/wrongly resolved | Locator failure or substitution cannot be mistaken for schema identity or conformance |

## 8. Compatibility and migration protocol candidate

A future LLMLang design review should require the following record for every schema change:

1. Exact writer schema identity and reader schema identity.
2. Encoding and format version, including relevant feature/edition settings.
3. Direction: writer→reader, not merely “v1 compatible with v2”.
4. Separate outcomes for wire decode, semantic interpretation, value preservation, unknown relay, source/API, ABI, and canonical identity.
5. Explicit handling of absent, null, explicit default, and uninitialized state.
6. Unknown field/case policy: reject, preserve opaquely, or map to fallback; if fallback is allowed, document information loss.
7. Migration function identity, preconditions, postconditions, idempotence, reversibility, and lossy projections.
8. Runtime/library/compiler versions and conformance test evidence.
9. Cache/fingerprint identity inputs and invalidation behavior.
10. Trust/authorization for schema publication and migration execution, separately from hashes.

For persisted data, a migration should be treated as a transformation with an explicit source version and target version, not an implicit side effect of deserialization. Read compatibility does not establish write compatibility; a successful migration does not establish reversibility; and an opaque relay does not establish that the old application can safely act on the new value.

## 9. Recommendations and non-decisions

Recommendations for subsequent prototype work:

1. Keep the three existing JSON fixtures as small semantic probes, but do not use them as evidence for real-format conformance.
2. Add real-runtime fixtures for Protobuf, Avro, and CBOR with pinned tool/runtime versions and captured old/new payloads.
3. Generate a directional compatibility matrix and report each dimension independently.
4. Include rename, deletion/reservation, numeric promotion/narrowing, nested unknowns, enum/union evolution, duplicate fields, and JSON bridge cases.
5. Test schema fingerprints separately from reader defaults, aliases, and migration metadata.
6. Prohibit generic hashes of serialized payloads unless a protocol-specific canonical data model and algorithm are explicitly defined.
7. Keep registry identifiers, schema fingerprints, wire-contract identities, and semantic hashes as separate typed concepts.
8. Require compatibility and migration tests to include both preservation and deliberate rejection cases.

This study does **not** select Protobuf, Avro, CBOR, JSON, or a custom LLMLang format. It does not select an Option/presence representation, unknown-case semantics, schema registry, compatibility promise (backward/forward/full), canonical encoding, hash envelope, migration mechanism, or ABI rule. No change to draft/ is authorized by these findings.

## 10. Quality-gate assessment

The Q1–Q5 labels below reuse the proposed vocabulary in the Scenario 0.2 quality-rules study; that vocabulary has not been adopted as project policy.

| Gate | Result | Reason |
|---|---|---|
| Q1 Traceable | Pass | Scenarios 109–111, glossary, official format documents, and RT areas are named. |
| Q2 Method inspectable | Pass | Source-based comparison and limits are explicit; no runtime tests are claimed. |
| Q3 Claims evidence-labelled | Pass | Normative format rules, cross-format analysis, candidate recommendations, and non-decisions are separated. |
| Q4 Adversarial coverage | Partial | Loss, stale metadata, unknown values, duplicate fields, narrowing, signatures, and migration paths are identified but not executed. |
| Q5 Decision-safe | Pass | No format, language rule, identity hash, or migration policy is selected. |

## 11. Sources

- Protocol Buffers, Field Presence (https://protobuf.dev/programming-guides/field_presence/), proto3 Language Guide — Updating a Message Type and reserved fields (https://protobuf.dev/programming-guides/proto3/), Enum Behavior (https://protobuf.dev/programming-guides/enum/), Encoding (https://protobuf.dev/programming-guides/encoding/), and Proto Serialization Is Not Canonical (https://protobuf.dev/programming-guides/serialization-not-canonical/).
- Apache Avro, Specification — schema declaration and schema resolution (https://avro.apache.org/docs/1.12.0/specification/#schema-resolution), Parsing Canonical Form for Schemas (https://avro.apache.org/docs/1.12.0/specification/#parsing-canonical-form-for-schemas).
- IETF, RFC 8949 — CBOR (https://www.rfc-editor.org/rfc/rfc8949.html), especially §§2, 4.2, 5.2–5.4, and 7.
- LLMLang Scenario 109 (RESEARCH-SCENARIO-109-OPTIONAL-PRESENCE-ROUND-TRIP.md), Scenario 110 (RESEARCH-SCENARIO-110-WIRE-SCHEMA-EVOLUTION-AND-DEFAULTS.md), Scenario 111 (RESEARCH-SCENARIO-111-UNKNOWN-WIRE-VARIANT-PRESERVATION.md), and Draft Glossary (../draft/GLOSSARY.md).

---

**Conclusion:** Scenarios 109–111 already establish useful bounded JSON observations. Scenario 134 shows why they do not establish a real wire compatibility policy: Protobuf, Avro, and CBOR make different choices about presence, schema lookup, unknown values, reader defaults, and canonicalization. The most consequential identity result is that a parsing fingerprint, evolution policy, registry locator, and semantic wire contract are distinct objects. The research is analytically complete within this source-review scope, while executable cross-format conformance and any LLMLang policy remain open.
