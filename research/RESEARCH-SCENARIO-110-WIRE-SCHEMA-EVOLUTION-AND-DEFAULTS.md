# Research Scenario 110 — Wire Schema Evolution and Defaults

**Status:** Finite executable compatibility fixture; no LLMLang wire policy selected
**Research area:** RT-04 data types, RT-05 interface identity, RT-13 serialization
**Updated:** 2026-11-20

## Question

When a producer adds a field to a serialized record, which combinations of old/new producer, old/new consumer, unknown-field policy, absent-field default, and explicit `null` behavior remain readable and preserve intended meaning?

## Fixture and results

`PROTOTYPES/RT-04-01/schema_evolution_model.py` defines version 1 with required integer `count`, and version 2 with `count` plus a Boolean `enabled` defaulted by the consumer when omitted. Producers emit compact JSON. Consumers can reject or ignore unknown keys; the v2 consumer separately rejects `null` or maps it to the absent-field default. Six focused tests cover the four basic producer/consumer version pairs, a 16-case finite cross-product, default changes, explicit values, null handling, and unknown fields.

| Producer → consumer | Strict unknown fields | Ignore unknown fields | Observation |
|---|---|---|---|
| v1 → v1 | Reads | Reads | Original required field is preserved |
| v1 → v2 | Reads, uses v2 default | Reads, uses v2 default | Adding a defaulted field can accept old payloads |
| v2 → v1 | Rejects new key | Reads `count`, drops `enabled` | Forward compatibility depends on explicit unknown-key policy and may lose new information |
| v2 → v2 | Reads both fields | Reads both fields | Version-aligned round trip preserves the new value |

Changing the v2 default changes the interpreted `enabled` value of old v1 payloads; it does not affect payloads that explicitly carry `enabled: false`. Explicit `null` is not omission under the reject policy. A separate null-as-absent policy maps it to the configured default. Unknown key `future` is distinct from an absent known `enabled` field: strict mode rejects it, while permissive mode ignores it.

These are properties of the tested policies, not universal compatibility laws. The `count` field remains required, and decode errors are kept as errors rather than replaced with defaults.

## Limits and next discriminators

The model is not a real schema language, LLMLang serializer, binary format, database migration, source/API compatibility test, or ABI/FFI experiment. It covers one added Boolean field, one integer field, JSON objects, and two hand-selected unknown/null policies. It does not model field removal/rename/type changes, duplicate keys, nested collections, unknown enum cases, signatures, canonical hashes, consumer side effects, or actual old binaries.

Next test versioned schema registries and migration functions, field rename/type widening, duplicate/unknown nested values, enum-case addition, canonical encoding, and whether compatibility metadata belongs in interface identity. Measure behavior and rejection separately from source and ABI compatibility.

## Reproduction

From repository root:

```sh
python -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_schema_evolution_model.py' -v
```
