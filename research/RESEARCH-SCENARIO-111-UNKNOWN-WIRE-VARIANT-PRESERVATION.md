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

## Limits and next discriminators

This fixture does not implement source-level open enums, exhaustiveness checking, a production wire format, signatures, canonical hashing, ABI/FFI, or application-level safety policy. It covers one JSON sum object and three hand-selected policies. Opaque preservation can support relays, but does not make an older application understand or safely act on a new case.

Next compare signed/canonical messages, nested unknown cases, enum payload evolution, projection/editing of opaque values, and strictness at trust boundaries. Separate “decode for relay” from “execute domain behavior,” and test what an old consumer does when it must branch on the value.

## Reproduction

```sh
python -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_unknown_variant_model.py' -v
```
