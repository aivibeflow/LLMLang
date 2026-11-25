# RT-04 — Opaque and erased provider result compatibility

Can a provider replace a hidden concrete type while keeping the visible factory signature and ordinary behavior? The fixture separately compiles a Rust library and consumers of its `Value::sum` operation. The two providers store the same four bytes inline or behind an `Rc`. The branch baseline is `02fc81aa32724bd7495eebcdb291aec552afe47c`. [Type abstraction alternatives](RESEARCH-SCENARIO-70-TYPE-ALIASES-NEWTYPE-AND-OPAQUE-ABSTRACTIONS.md)

Four factory signatures expose an opaque result or a boxed trait object, each with and without an explicit `Send` bound. An ordinary client uses the advertised method. A second client also passes the value to a generic function requiring `Send`. Accepted clients report the method result and `size_of_val` for the returned value. The compile-time `Send` check needs no concurrent execution.

| Factory signature | Inline provider | `Rc` provider | `Send` client |
|---|---|---|---|
| `impl Value` | Accepted, 4 B | Accepted, 8 B | Accepts inline, rejects `Rc` |
| `impl Value + Send` | Accepted, 4 B | Rejected at provider | Accepts inline |
| `Box<dyn Value>` | Accepted, 16 B | Accepted, 16 B | Rejects both |
| `Box<dyn Value + Send>` | Accepted, 16 B | Rejected at provider | Accepts inline |

Six provider variants compile. All six corresponding ordinary clients return 10. Three of the six clients that require `Send` compile and return 10. Every blocked client or provider reports E0277. With an opaque signature that omits the bound, the compiler infers the hidden type's `Send` property across the crate boundary. Replacing that hidden type therefore changes which clients type-check. The explicit bound moves that compatibility check to the provider. Trait-object erasure without the bound exposes neither provider's `Send` property through the returned object. [Complete build and observation receipt](OPAQUE-PROVIDER-TYPES-01/evidence.json)

The size measurements describe the returned value on this target, including the fat boxed trait-object handle. They exclude heap allocations. The result distinguishes the public method contract, auto-trait guarantees and physical representation. It covers recompiling the same client source separately against each candidate library. Dynamic binary linkage, reuse of a previously compiled client, representation stability across toolchains and LLMLang's abstraction policy remain open. [Rust opaque return semantics](https://doc.rust-lang.org/reference/types/impl-trait.html#abstract-return-types) · [Type and data model issue](https://github.com/aivibeflow/LLMLang/issues/324)

## Reproduction

Use rustc 1.85.1 at commit `4eb161250e340c8f48f66e2b929ef4a5bed7c181` with LLVM 19.1.7 on x86-64 Linux and CPython 3.12.14. Hash seeds 1 and 2 produced identical receipts.

```bash
fixture=research/language-design/RT-04/OPAQUE-PROVIDER-TYPES-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" --rustc /path/to/pinned/rustc > /tmp/llmlang-rt04-opaque-provider.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt04-opaque-provider.json
```
