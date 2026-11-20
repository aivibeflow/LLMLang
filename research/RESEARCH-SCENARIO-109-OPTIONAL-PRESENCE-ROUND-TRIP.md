# Research Scenario 109 — Optional Presence at a Serialization Boundary

**Status:** Bounded executable encoding comparison; no LLMLang representation selected
**Research area:** RT-03 value/error semantics, RT-04 algebraic types, RT-13 serialization/FFI
**Updated:** 2026-11-20

## Question

Can candidate value representations preserve the distinction between an omitted JSON field, an explicit `null`, and a present integer across a decode/encode boundary? Keep malformed input and an uninitialized local distinct from all three value states.

## Fixture and findings

`PROTOTYPES/RT-04-01/optional_presence_model.py` defines a deliberately narrow JSON adapter for one integer field. Eight focused tests cover absent, null, value, malformed/type-invalid input, boolean-vs-integer decoding, encoding round-trip, representation collisions, and uninitialized reads.

Under the fixture convention, a one-level `Option<Int>` maps both omission and explicit null to `None`, so that representation cannot reconstruct the original JSON distinction. A nested `Option<Option<Int>>` can encode absent, null, and value as three separate constructors. A presence bit paired with a nullable payload also distinguishes all three. These are encoding observations under the stated convention, not a claim that nested optionals must mean absence/null in every language or serializer.

Decode failures are modeled as an outer error case, separate from a successfully decoded absent field. Reading an uninitialized local raises a separate initialization failure; it is not represented as an optional value. JSON round trips preserve the three valid states in this fixture.

## Limits and next discriminators

This is not an LLMLang parser, serializer, schema implementation, type checker, FFI/ABI experiment, or normative nullability policy. It covers one object field and integer payload, not defaults, duplicate keys, unknown fields, nested objects, collections, database absence, pointer niches, or versioned schema evolution. No layout or performance inference follows.

Next compare a versioned schema with defaults, repeated/unknown fields, nested collections, C nullable-pointer conversion, and API evolution. Specify whether omission is an input-only fact, a persistent value state, or an error; specify presence/default policy independently of `Option` layout.

## Reproduction

From the repository root:

```sh
python -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_optional_presence_model.py' -v
```
