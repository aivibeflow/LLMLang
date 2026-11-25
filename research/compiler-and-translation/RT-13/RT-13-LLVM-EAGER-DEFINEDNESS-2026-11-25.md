# RT-13 — Guarded operations and LLVM eager definedness

When can an LLVM lowering replace a branch with an eager computation followed by `select`? The fixture compares checked byte shifts and unsigned byte division under six candidate IR policies. Both source operations return a tagged refusal for their invalid operands. The branch baseline is `14d380f345025fb07856fd48800856eaacf05e5f`. [LLVM undefined behavior manual](https://llvm.org/docs/UndefinedBehavior.html) · [LLVM backend issue](https://github.com/aivibeflow/LLMLang/issues/330)

An unchecked `shl i8` produces poison for a count at least 8. LLVM `select` observes only the selected operand, so the chosen refusal remains defined in the masked-shift variant. Unsigned division by zero triggers immediate undefined behavior at the division. The sanitized candidate selects a safe divisor of 1 before computing, then selects the checked return value. The two negative division variants compute before either masking or freezing the result. [LLVM shift and divide semantics](https://llvm.org/docs/LangRef.html#binary-operations) · [Exact input IR](LLVM-DEFINEDNESS-BOUNDARIES-01/policies.ll)

| Variant | Defined byte-pair inputs | Native outputs checked at each optimization level |
|---|---:|---:|
| Guarded shift | 65,536 | 65,536 |
| Eager shift with unselected poison | 65,536 | 65,536 |
| Guarded division | 65,536 | 65,536 |
| Eager division with sanitized operand | 65,536 | 65,536 |
| Eager division followed by output selection | 65,280 | 65,280 |
| Eager division followed by freeze and output selection | 65,280 | 65,280 |

All six functions pass the LLVM structural verifier. The two unsanitized division variants have 256 zero-divisor inputs outside their IR defined domain. The runner excludes those cases from native execution and checks both controls on their remaining defined inputs. All 392,704 executed calls at each optimization level match the source observation for their checked input scope. The matched guarded and total eager variants have identical output transcripts per operation. [Definedness and exact native receipts](LLVM-DEFINEDNESS-BOUNDARIES-01/evidence.json)

A source-to-IR validation gate needs the definedness preconditions for the operations that actually execute in the LLVM model. Poison masking can preserve a checked branch on a defined `select` condition. Later output masking and freezing leave a prior immediate-UB operation outside the source contract. The experiment covers concrete byte inputs, pure arithmetic and x86-64 code generation. General poison propagation, pointer operands, optimizer proof certificates and other target profiles remain open. [LLVM backend architecture](LLVM-BACKEND-ARCHITECTURE.md)

## Reproduction

Use CPython 3.12.14, Clang 23.1.1 at LLVM revision `6dfe1677ab8dffbc6ec13d53a1e0215d75147689`, and Debian LLVM `opt` 19.1.7. Clang builds the original IR at optimization levels 0 and 3. Hash seeds 1 and 2 produced identical evidence.

```bash
fixture=research/compiler-and-translation/RT-13/LLVM-DEFINEDNESS-BOUNDARIES-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" --clang /path/to/pinned/clang --opt /path/to/opt-19 > /tmp/llmlang-rt13-definedness.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt13-definedness.json
```
