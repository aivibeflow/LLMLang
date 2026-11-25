# RT-13 — C++ value layout, destruction and return ABI

Can two versions of a C++ record have the same layout and exported symbol while requiring different call sequences? The fixture changes only whether a two-field record has a nontrivial destructor and compares its by-value return with an explicit C output-parameter facade. The branch baseline is `52f397d72ddfbec6e9bd85aff68dde2300c4bb94`. [Itanium C++ return ABI](https://itanium-cxx-abi.github.io/cxx-abi/abi.html#return-values) · [Backend selection issue](https://github.com/aivibeflow/LLMLang/issues/329)

Clang compiles the provider and emits its LLVM signatures. GNU C++ compiles a matched caller against each record definition. A second caller is compiled as C once and linked to both matching facade symbols. The two record versions have size 8, alignment 4 and member offsets 0 and 4. Both providers expose the same mangled name for the C++ factory. [Record and facade declaration](CPP-DESTRUCTOR-ABI-01/record.h)

| Provider record | LLVM return carrier of the by-value factory | Explicit C facade parameters | Observed destructor count per client run |
|---|---|---|---:|
| Trivial destruction | Direct `i64` result | Input and two output pointers | 0 |
| Nontrivial destruction | Hidden result pointer marked `sret` | Input and two output pointers | 16 |

All four provider and optimization combinations produce the expected payloads through both paths, for 128 calls. The nontrivial by-value caller owns the returned record until the end of its loop iteration. In the facade the provider owns the record and writes only the two scalar fields into caller-provided storage. Both routes record one destruction per produced nontrivial record. [Exact ABI and outcome receipts](CPP-DESTRUCTOR-ABI-01/evidence.json)

Size, alignment, field locations and exported name leave a difference in the by-value call contract. A typed interface needs to account for construction and destruction properties when binding C++ values, or use an explicit C facade whose separate parameter and ownership contracts are part of the interface. The fixture covers matched calls on x86-64 Linux. Other ABIs, exceptions across boundaries, opaque resources, copy or move changes, and broader target selection remain open. [Native layout comparison](RT-13-NATIVE-RECORD-LAYOUT-2026-11-25.md)

## Reproduction

Use CPython 3.12.14, Clang 23.1.1 at LLVM revision `6dfe1677ab8dffbc6ec13d53a1e0215d75147689`, and GCC and G++ 14.2.0 (Debian 14.2.0-19). The runner uses Clang for provider object and signature generation, GCC for the C client, and G++ for matching C++ calls and linkage. Hash seeds 1 and 2 produced identical receipts.

```bash
fixture=research/compiler-and-translation/RT-13/CPP-DESTRUCTOR-ABI-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" --clang /path/to/pinned/clang > /tmp/llmlang-rt13-cpp-destructor-abi.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt13-cpp-destructor-abi.json
```
