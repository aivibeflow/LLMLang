# RT-13 — LLVM progress promises and source divergence

When may a lowering add an LLVM progress promise to a source loop that can run forever? This study compares four closely matched IR programs and records the optimizer's exact treatment of their wait loops. The branch baseline is `5a17a7f860c6f54c40c809e7cc2fb4b63449d78f`. [Source recursion and fuel](../../language-design/RT-03/RESEARCH-SCENARIO-36-RECURSION-TERMINATION-AND-FUEL.md) · [LLVM backend issue](https://github.com/aivibeflow/LLMLang/issues/330)

The source fixture returns 7 when the input is 1. Otherwise it takes a self-loop. The unannotated IR keeps this silent divergence. Two controls assert progress with the function attribute or loop metadata. A fourth route adds the function attribute and performs a volatile read on each iteration. LLVM's progress contract admits continued interaction with the environment through a volatile access. An infinite silent loop violates the asserted promise. [LLVM function attributes](https://llvm.org/docs/LangRef.html#function-attributes) · [LLVM loop progress metadata](https://llvm.org/docs/LangRef.html#llvm-loop-mustprogress-metadata)

| Exact IR variant | Wait back edge after O3 | Optimizer assumes input is 1 | Volatile load retained |
|---|---|---|---|
| Unannotated silent loop | Yes | No | No |
| Function progress promise | No | Yes | No |
| Loop progress promise | No | Yes | No |
| Function progress with volatile loop | Yes | No | Yes |

All four loops are present in the O0 output. Under O3, the two silent progress controls replace the wait path with `llvm.assume` of the returning condition. The volatile control keeps both the back edge and the read. All eight linked executions on the terminating input return 7. The wait paths are inspected through exact IR. The runner tests the terminating input natively and reports the progress promise separately. [Input IR](LLVM-PROGRESS-BOUNDARIES-01/progress.ll) · [Optimizer and native observations](LLVM-PROGRESS-BOUNDARIES-01/evidence.json)

A conservative lowering omits a progress promise when the admitted source behavior includes silent divergence. It can use the promise when the source independently establishes termination, unwinding or the relevant observable interactions. Function and loop annotations need their respective scopes. The fixture covers one self-loop and one volatile access on one optimizer profile. General effectful progress, backend timing and termination proof integration remain open. [LLVM backend architecture](LLVM-BACKEND-ARCHITECTURE.md)

## Reproduction

Use Debian LLVM `opt` 19.1.7, Clang 23.1.1 at revision `6dfe1677ab8dffbc6ec13d53a1e0215d75147689`, and CPython 3.12.14. The harness verifies both sides of the O0 and O3 pipelines and compiles the inspected IR for the native checks. Two Python hash seeds produced identical results.

```bash
fixture=research/compiler-and-translation/RT-13/LLVM-PROGRESS-BOUNDARIES-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" --clang /path/to/pinned/clang --opt /path/to/opt-19 > /tmp/llmlang-rt13-progress.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt13-progress.json
```
