# RT-04 — Numeric inference and explicit signature boundaries

Can a later use change the inferred type of an earlier declaration? When does an annotation turn that change into a compile error? This study compiles seven matched Rust and Go cases. The branch baseline is `f14f279b73f7e5e0923a374410a1d46afe0da658`. [Type inference and annotation alternatives](RESEARCH-SCENARIO-60-TYPE-INFERENCE-SCOPE-AND-ANNOTATIONS.md)

Each fixture observes the type and value of the same numeric local. The first edit adds a later call requiring an unsigned 64-bit argument. The call's body is empty. The next cases add a 32-bit annotation and an explicit conversion. The final cases test a function with a concrete return type and one with a placeholder or omitted return type.

| Source condition | Rust 1.85.1 | Go 1.24.13 |
|---|---|---|
| Inferred local initialized with 9 | `i32:9` | `int:9` |
| Later use requires unsigned 64 bits | `u64:9` | Rejects passing `int` as `uint64` |
| Local annotated unsigned 32 bits | `u32:9` | `uint32:9` |
| Annotated local passed directly | Type mismatch, E0308 | Rejects passing `uint32` as `uint64` |
| Annotated local passed through explicit conversion | Local remains `u32:9` | Local remains `uint32:9` |
| Concrete unsigned 64-bit function result | `u64:9` | `uint64:9` |
| Placeholder or omitted function result | Rejects placeholder, E0121 | Rejects extra return value |

Rust's local literal remains available to a later constraint in this fixture. Go fixes the type of the short declaration to the default `int` and checks the later argument against that type. Both annotations preserve the local type across the edit, with an explicit conversion at the call when required. A Rust placeholder in a public item type and an omitted Go result have different syntax rules. Neither admits the proposed inferred return type. [Generated-source inputs and observed results](INFERENCE-BOUNDARIES-01/run.py) · [Machine-readable receipt](INFERENCE-BOUNDARIES-01/evidence.json)

The study distinguishes constraints within a local inference scope from explicit signatures. It tests numeric literals and monomorphic functions on one native platform. It leaves generic inference, incremental invalidation across separate modules, other literal kinds and language selection open. [Type and data model issue](https://github.com/aivibeflow/LLMLang/issues/324)

## Reproduction

Use rustc 1.85.1 at commit `4eb161250e340c8f48f66e2b929ef4a5bed7c181`, Go 1.24.13 linux/amd64 and CPython 3.12.14. The official Go archive SHA-256 used here was `1fc94b57134d51669c72173ad5d49fd62afb0f1db9bf3f798fd98ee423f8d730`. The runner compares diagnostics and executes every accepted binary. Two hash seeds yielded identical receipts. [Go releases](https://go.dev/dl/)

```bash
fixture=research/language-design/RT-04/INFERENCE-BOUNDARIES-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" --rustc /path/to/rustc --go /path/to/go --cache /tmp/llmlang-rt04-gocache > /tmp/llmlang-rt04-inference.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt04-inference.json
```
