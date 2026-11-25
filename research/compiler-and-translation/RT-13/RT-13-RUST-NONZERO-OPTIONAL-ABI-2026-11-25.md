# RT-13 — Rust optional niches and explicit C ABI tags

Where can a Rust backend expose an optional scalar directly to C, and when must the interface preserve a separate tag? This fixture compares the documented `Option<NonZeroU32>` carrier with a `repr(C)` tagged value and two compile-time refusal controls. The branch baseline is `0b73ea8f85fbe33a126429c8b7c98d76a9ff2915`. [Rust NonZeroU32 layout and ABI](https://doc.rust-lang.org/std/num/type.NonZeroU32.html#layout) · [Backend selection issue](https://github.com/aivibeflow/LLMLang/issues/329)

The C client passes `uint32_t` to both Rust niche entry points and checks identity and presence. The documented nonzero domain leaves word zero for absence. The second route passes a two-field tagged record and distinguishes absence, any present 32-bit word, and malformed tags. The C and Rust layout queries agree on size 8 and alignment 4. [Rust bridge](RUST-NONZERO-OPTIONAL-ABI-01/bridge.rs) · [Independent C client](RUST-NONZERO-OPTIONAL-ABI-01/client.c)

Each optimization level checks 260 input words for the niche carrier and 1,040 tag and word combinations for the explicit record. The two modes produce identical transcripts. The niche route preserves each native word and reports only zero as absent. The tagged route distinguishes absence from present zero and rejects both a noncanonical payload under the absent tag and unknown tags. With warnings treated as errors, rustc issues `improper_ctypes_definitions` for direct `Option<u32>` and for nested `Option<Option<NonZeroU32>>` in this profile. [Exact counts and compiler diagnostics](RUST-NONZERO-OPTIONAL-ABI-01/evidence.json)

A direct carrier requires the exact documented source value domain and ABI. The explicit tag accommodates a payload domain that includes zero. The experiment covers value types, compatible C calls and selected x86-64 Linux profiles. Pointer ownership, reserved tags for version evolution, other ABIs and general Rust backend selection remain open. [Nested optional byte comparison](../../language-design/RT-04/RT-04-NESTED-OPTIONAL-BYTE-ABI-2026-11-25.md) · [Type and data model issue](https://github.com/aivibeflow/LLMLang/issues/324)

## Reproduction

Use rustc 1.85.1 at commit `4eb161250e340c8f48f66e2b929ef4a5bed7c181`, GCC 14.2.0 (Debian 14.2.0-19) and CPython 3.12.14 on x86-64 Linux. The runner builds the Rust library at optimization levels 0 and 2 and verifies each C call's output. Hash seeds 1 and 2 produced byte-identical receipts.

```bash
fixture=research/compiler-and-translation/RT-13/RUST-NONZERO-OPTIONAL-ABI-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" --rustc /path/to/pinned/rustc > /tmp/llmlang-rt13-rust-niche.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt13-rust-niche.json
```
