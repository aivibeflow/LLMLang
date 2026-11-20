# Research Scenario 114 — Release Sequences and Acquire Relay

**Status:** Bounded axiom-driven outcome fixture with official C++20 prior art; no LLMLang atomic contract selected  
**Research area:** RT-04 ownership/effects/memory model; RT-10 runtime  
**Updated:** 2026-11-20

## Question

When can an acquire operation synchronize with a release operation indirectly through an intervening atomic read-modify-write (RMW), and what breaks that relay? This distinction matters because an acquire reading the same numeric flag value does not itself prove that it read from a release sequence.

## C++20 contract relevant to the fixture

The current C++ draft describes a release sequence as a maximal contiguous subsequence of one atomic object's modification order, headed by a release operation, where every following operation is an atomic RMW. An acquire operation that reads a value written by a side effect in that release sequence synchronizes with its head. Thus a relaxed RMW may relay the release sequence even though it is not itself a release operation. Since C++20, a relaxed plain store after the head is not an RMW and ends the sequence for subsequent modifications. Before C++20, however, writes by the same thread that performed the release head could also extend the sequence. This version change means an acquire reading an identical numeric value from a same-thread plain store may synchronize with the release under the older rule but not under C++20. These rules interact with modification order, read-from, happens-before, and coherence; a numeric value alone is insufficient to establish the synchronization edge.

Source: [C++ draft — multithreaded executions and release sequences](https://eel.is/c++draft/intro.multithread).

## Discriminating fixture

Use atomic `payload` and atomic `flag`, both initially zero:

```text
Writer:                         Relay:                   Reader:
payload.store(1, relaxed);      flag.fetch_add(1, relaxed);  flag.load(acquire);
flag.store(1, release);         // if in modification order   payload.load(relaxed);
```

The writer's release store heads a release sequence. If the relay RMW follows it in `flag`'s modification order and the reader's acquire reads from that RMW, the acquire synchronizes with the head, so the subsequent atomic payload load cannot observe the older initial write. In the contrast case, a relaxed plain store to `flag` intervenes and writes the value the reader acquires; that store breaks the release sequence, so this fixture does not derive a release/acquire edge to the writer's payload store.

| Explicit read-from premise | Release/acquire edge from writer? | Allowed payload load outcomes in fixture |
|---|---:|---|
| Acquire reads the relay RMW that belongs to the release sequence | Yes, before and since C++20 | `{1}` |
| Acquire reads a relaxed plain store by a different thread after the release head | No edge from the original release | `{0, 1}` |
| Acquire reads a relaxed plain store by the release-head thread after the release | Yes before C++20; no since C++20 | `{1}` before C++20; `{0, 1}` since C++20 |

The payload is atomic to avoid a data race in the no-edge comparison. `0` means the read may still observe the initial payload write; the relation does not claim that the compiler or machine realizes both cases in every execution.

## Executable evidence and limits

[`release_relay_payload_outcomes`](PROTOTYPES/RT-04-01/rt04_store_buffering.py) maps an explicitly supplied read-from/release-sequence premise to the outcome set; [`same_thread_plain_store_is_release_sequence_member`](PROTOTYPES/RT-04-01/rt04_store_buffering.py) encodes the C++17 versus C++20 membership change. Tests check RMW relay, version-specific same-thread plain-store behavior, and payload outcomes. The fixture does not infer modification order, RMW membership, or read-from from source code; it does not implement the full C++ or Rust memory model, nor run a compiler or target hardware. Its purpose is to pin down the synchronization premise and the language-version compatibility difference, not to confuse equal flag values with synchronization provenance.

This adds a discriminating memory-model case to Scenario 113; it does not select LLMLang's memory model. A complete proposal must define release-sequence membership and evolution, acquire read-from conditions, atomic modification order, all coherence rules, fences, mixed accesses, and interactions with channels/locks/ownership. For implementation validation, bind litmus outcomes to a formal model and compiler/backend versions across targets.

## Sources

- [C++ draft — release sequences and synchronization](https://eel.is/c++draft/intro.multithread)
- [WG21 P0982R1 — Weaken Release Sequences (C++20 proposal)](https://open-std.org/jtc1/sc22/wg21/docs/papers/2018/p0982r1.html)
- [Rust `std::sync::atomic::Ordering`](https://doc.rust-lang.org/std/sync/atomic/enum.Ordering.html)
- [cppreference — release sequence (C++20 definition)](https://cppreference.com/w/cpp/atomic/memory_order.html)
