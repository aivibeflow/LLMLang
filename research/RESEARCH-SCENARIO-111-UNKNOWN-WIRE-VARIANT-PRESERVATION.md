# Research Scenario 111 — Unknown Wire Variant Preservation

**Status:** Bounded executable policy comparison; no LLMLang variant policy selected
**Research area:** RT-04 sum types and pattern matching, RT-05 interface evolution, RT-13 serialization
**Updated:** 2026-11-20

## Question

When a newer producer sends a newly added sum-type case to an older consumer, should the consumer reject it, map it to a generic fallback, or retain the unknown case opaquely so it can relay the message?

## Fixture and results

`PROTOTYPES/RT-04-01/unknown_variant_model.py` defines v1 cases `ready` and `failed(code)`, and uses `suspended(until, meta)` as a case unknown to that consumer. Seven focused tests cover existing cases, each unknown-case policy, nested extension payloads, malformed known cases, missing discriminators, and relay encoding.

| Unknown-case policy | Decode result | Relay behavior | Cost or risk |
|---|---|---|---|
| Reject | Decode error | No relay | Safest when the application must understand every case, but breaks old consumers on additive cases |
| Fallback | Generic `other` | Emits only `other` | Continues execution but discards the original case and payload; business logic may treat a significant state as generic |
| Preserve opaque | Stores the complete unknown JSON object | Re-emits its parsed structure | Enables semantic forwarding, but the consumer cannot safely interpret the new case |

The preserve policy retains the unknown object's JSON structure through parse/re-encode, including nested payload values. It does not retain the original byte spelling, whitespace, or key order: the fixture serializer canonicalizes key order and separators. Malformed payloads for known cases and objects without a discriminator remain decode errors under every policy; they are not misclassified as forward-compatible unknown cases.

## Prior-art comparison

| Format / rule | Unknown-case behavior | Implication |
|---|---|---|
| Protocol Buffers proto3 open enums | Unknown numeric enum values are retained in the message and serialized again; their API representation varies by generated language. | A wire-level numeric enum can preserve values without a symbolic fallback. Application switches still need to handle values outside the locally declared set. |
| Protocol Buffers closed enums | Unknown repeated enum numbers may be moved into the unknown-field set and re-emitted after recognized values, changing their original position. | Preservation of values is not always preservation of order or exact collection semantics. |
| Apache Avro schema resolution | An unknown writer enum symbol maps to the reader enum's declared default if present; otherwise resolution errors. | A fallback is schema-directed and readable, but loses the unknown symbol unless separately carried. |
| CBOR generic decoder | RFC 8949 permits returning the unknown item's type/value (and decoded tagged item) with an indication that the tag/simple value is unrecognized; generic encoders/decoders are expected to forward unknown tags/simple values. Layered protocols may require lower layers to forward data as-is. | This explicitly separates transport/relay from application understanding, and gives an opaque forwarding path. |

These formats are not interchangeable: Protobuf has numeric field/value encoding and generated unknown-field behavior; Avro resolves against writer and reader schemas; CBOR defines generic data items plus protocol-level semantics. The Python JSON fixture demonstrates only the reject/fallback/opaque distinction, not those formats' actual runtime behavior.

## Sources

- [Protocol Buffers proto3 guide — enumerations and unrecognized values](https://protobuf.dev/programming-guides/proto3/#enumerations), consulted 2026-11-20.
- [Protocol Buffers Enum Behavior — closed-enum ordering and open/closed rules](https://protobuf.dev/programming-guides/enum/), consulted 2026-11-20.
- [Apache Avro specification — schema resolution](https://avro.apache.org/docs/current/specification/#schema-resolution), consulted 2026-11-20.
- [RFC 8949 §5.2 and §5.4 — generic decoders and validity/evolution](https://datatracker.ietf.org/doc/html/rfc8949#section-5.2), consulted 2026-11-20.

## Limits and next discriminators

This fixture does not implement source-level open enums, exhaustiveness checking, a production wire format, signatures, canonical hashing, ABI/FFI, or application-level safety policy. It covers one JSON sum object and three hand-selected policies. Opaque preservation can support relays, but does not make an older application understand or safely act on a new case.

Next compare signed/canonical messages, nested unknown cases, enum payload evolution, projection/editing of opaque values, and strictness at trust boundaries. Separate “decode for relay” from “execute domain behavior,” and test what an old consumer does when it must branch on the value.

## Reproduction

```sh
python -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_unknown_variant_model.py' -v
```
