# RT-04 — Static separation and checked disjoint mutable borrows

When can a caller pass two writable references to the same operation? This native Rust fixture compares statically disjoint fields, direct indexing of one array, and two indices checked against one existing mutable slice. The branch baseline is `c65c7a944a529131c6b2756b831e07cd1fe09717`. [Ownership and capability alternatives](RT-04-TYPE-EFFECT-OWNERSHIP-AND-CAPABILITY-ALTERNATIVES.md)

The fixture operation writes 91 through its first mutable reference and 92 through its second. The checked adapter requires both indices to be in bounds and distinct. It splits the slice at the larger index and returns one mutable reference from each half, preserving argument order. It refuses overlap and out-of-bounds requests before any write. The borrow lifetime is tied to the input slice. [Rust slice API](https://doc.rust-lang.org/1.85.1/std/primitive.slice.html#method.split_at_mut)

| Input to the operation | Observed compiler or runtime result |
|---|---|
| Two named tuple fields | Compiles and writes 91 and 92 to the two fields |
| Two direct indices of one array, even constants 0 and 1 | Compile error E0499 |
| Two checked, in-bounds distinct indices | Compiles and writes exactly at the requested ordered positions |
| Two checked but equal in-bounds indices | Returns overlap and leaves every element unchanged |
| At least one index outside the slice | Returns out-of-bounds and leaves every element unchanged |
| Checked references used after the input array's scope ends | Compile error E0597 |

Each native build runs 180 cases, using slice lengths zero through four and both indices from zero through five. An independent Python oracle compares every disposition and resulting slice. Both optimization levels admit the same 20 pairs and refuse the same 10 overlaps and 150 out-of-bounds cases. They produce identical complete observation digests. [Rust fixture](DISJOINT-BORROWS-01/fixture.rs) · [Compiler and native results](DISJOINT-BORROWS-01/evidence.json)

The evidence supports an explicit checked disjoint-view API for callers whose indices become known at runtime. The API turns a checked relation into two borrows while retaining the original lifetime boundary. The experiment covers one Rust release, plain slices, and single-threaded mutation. General alias analysis, foreign memory, interaction with asynchronous execution, and selection of LLMLang ownership rules remain open. [Type and data model issue](https://github.com/aivibeflow/LLMLang/issues/324)

## Reproduction

The runner used rustc 1.85.1 at commit `4eb161250e340c8f48f66e2b929ef4a5bed7c181` with LLVM 19.1.7 on x86-64 Linux. It compiles at optimization levels 0 and 2 and checks the structured diagnostics separately. CPython 3.12.14 produced identical receipts with hash seeds 1 and 2.

```bash
fixture=research/language-design/RT-04/DISJOINT-BORROWS-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" --rustc /path/to/pinned/rustc > /tmp/llmlang-rt04-disjoint-borrows.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt04-disjoint-borrows.json
```
