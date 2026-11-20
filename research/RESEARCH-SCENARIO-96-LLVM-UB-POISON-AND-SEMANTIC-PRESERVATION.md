# Scenario 96 — LLVM UB, Poison, and Semantic Preservation

**Status:** Evidence-linked backend comparison and discriminator design; no LLMLang behavior or backend selected
**Research areas:** RT-03 semantics, RT-07 proof boundary, RT-09 compiler/IR, RT-13 target preservation
**Updated:** 2026-11-19

## 1. Question and scope

Can LLMLang use LLVM as an optimizing backend without accidentally adopting LLVM IR's poison and undefined-behavior rules as source-language behavior? This is a semantic-preservation question, not a general evaluation of LLVM's speed or maturity. LLVM IR is an input language with its own defined, poison, and immediate-UB cases. A frontend must encode the source contract into that IR; matching instruction names or machine behavior on ordinary inputs is insufficient.

The relevant source choices include integer overflow, division edge cases, shifts, pointer provenance and bounds, initialization/validity, and floating-point assumptions. Scenario 45/78 compare numeric source policies; Scenario 72 addresses layout/ABI. This study isolates the obligations introduced by LLVM lowering and optimization. It does not decide whether unsafe/unchecked source behavior is permitted.

## 2. The important distinction: source UB is a contract; LLVM poison is an IR value

LLVM's UB manual describes immediate UB and deferred UB (`undef` and poison), with `freeze` constraining deferred nondeterminism. LLVM uses these states both for source situations whose result is intentionally unconstrained and as optimizer constraints guaranteed by a frontend. An operation marked `nsw`/`nuw` returns poison when the corresponding overflow occurs. Poison may propagate and can become immediate UB when used by operations with UB preconditions. Thus “the hardware instruction wraps” does not make an `nsw` operation wrap in LLVM semantics, and poison is not a runtime exception that can be caught.

The LLVM Language Reference gives plain integer `add` modulo-2^n behavior, but adds `nsw` or `nuw` change overflowing executions to poison. The IR also has memory/pointer promises such as `inbounds` GEP and attributes that give optimizers facts about validity, aliasing, alignment, or dereferenceability. Those promises must follow from LLMLang's proven source conditions; they cannot be added merely because they improve optimization.

## 3. Prior-art comparison

| System/layer | Relevant behavior | Design implication and limit |
|---|---|---|
| LLVM IR | Plain fixed-width integer `add`/`sub`/`mul` produce modulo-width results. `nsw`/`nuw` produce poison on violating their no-overflow assertions. LLVM distinguishes immediate UB from deferred poison/undef; `freeze` prevents some deferred values from changing arbitrarily. | A backend can express wrapping arithmetic directly, but checked, trapping, or source-UB arithmetic needs a deliberate encoding. Source-language behavior is not inherited automatically from LLVM's IR contract. |
| Rust source language | The Reference says integer `+`, `-`, `*` and certain other operators panic on overflow when compiled with debug mode / overflow checks; the signed minimum divided or remaindered by `-1` is checked even when overflow checks are disabled. Rust also has a separate unsafe validity/provenance model; its own Reference cautions that the unsafe-code UB list is not exhaustive and lacks a complete formal model. | One language may expose profile-sensitive arithmetic behavior while still distinguishing it from unsafe pointer/value validity. Lowering must preserve the exact selected profile contract, not equate every source exceptional case with LLVM poison. |
| WebAssembly Core | Integer add/sub/mul are modulo 2^N. Integer division is partial for division by zero and for signed minimum divided by -1. Linear memory accesses trap when the accessed bytes are outside current memory bounds. | A portable abstract machine can define wrapping arithmetic and explicit traps for selected partial operations while keeping memory fault behavior explicit. This demonstrates a contract different from general LLVM poison, not a claim that Wasm is the desired LLMLang target. |

The systems differ in several independent ways: whether an edge case returns a defined value, produces a language-level error/panic, traps, or permits optimizer assumptions; whether that behavior is profile-dependent; and whether the invalidity concerns arithmetic or pointer/value provenance. A single umbrella label “undefined” hides these distinctions.

## 4. Candidate source contracts and LLVM mappings

These are independent arithmetic/memory axes, not complete language profiles:

| Source contract candidate | Illustrative LLVM mapping | Main proof/measurement obligation |
|---|---|---|
| **W — Wrapping integer operations** | Plain LLVM integer arithmetic with no `nsw`/`nuw`; division and shifts still require separately defined edge rules. | Confirm signed/unsigned operations and constants follow the language's modulo-width contract under every optimization level and target. |
| **C — Checked operation with recoverable result** | Explicit overflow predicates or LLVM overflow intrinsics; branch to construct the source error/result. Do not replace the check with a no-overflow promise. | Verify all overflow paths return the specified value/error and no optimizer removes or reorders observable failure behavior. |
| **T — Defined trap/panic on violation** | Explicit condition, then a defined runtime trap/panic path; the normal-path IR may carry facts only after the guard establishes them. | Compare trap timing, cleanup, unwind/abort policy, and behavior in optimized builds; connect to Scenario 65. |
| **U — Source-level undefined behavior for a documented precondition violation** | LLVM poison/UB flags may represent a proven source precondition, but only when the frontend's proof/typing model establishes the implication and source contract permits the optimizer latitude. | Show the source program is genuinely outside the defined contract; test that safe code cannot reach the precondition and that diagnostics/unsafe boundaries are explicit. |
| **M — Memory-safe checked access** | Check index/length, allocation bounds, alignment and validity as required; use `inbounds` or dereferenceability attributes only after proving their exact preconditions. | Prove source checks dominate accesses after optimization; retain object/provenance conditions, not just numerical address bounds. |

These mappings are sketches. The same source program may require combinations: a checked overflow in safe code, a trapping division edge, wrapping bit operations, and a memory-safe indexing check. LLVM `freeze` is not a general-purpose source-level error recovery operation; its use must be justified against the language semantics of an otherwise poison value.

## 5. Minimal semantic-preservation corpus

Use a small, shared source corpus with reference semantics and IR witnesses. For each case, compare interpreter/reference result to unoptimized and optimized LLVM, and if available a second backend. Pin LLVM version, target triple, target features, flags, and optimization pipeline.

1. **Overflow:** `MAX + 1`, `MIN - 1`, `MIN * -1`, unsigned overflow, constant folding, and overflow in a dead branch. Distinguish wrap, typed error, trap, and source UB candidates.
2. **Division/remainder:** divisor zero; signed `MIN / -1` and `MIN % -1`; check whether failure occurs before any later observable effect.
3. **Shifts:** negative or at-least-width shift counts, for both signed and unsigned values, with bounds cases at 0, width-1, width, and larger.
4. **Memory:** index equal to length; one-past pointer formation versus dereference; arithmetic address overflow; misalignment; null/dangling pointer; uninitialized or invalid enum/bool discriminant; safe code versus explicitly unsafe code.
5. **Optimization-sensitive facts:** overflow result branches, pointer comparisons, aliasing, `select` with poisoned unselected branch, `freeze`, `inbounds` GEP, and `assume`/attribute propagation. Include cases where a defined source result is used after the edge case.
6. **Floating point:** test separately under Scenario 78's strict/relaxed profiles; do not confuse LLVM `fast-math` flags with integer poison or import the backend's default FP latitude into source rules.

For each case, declare source-level expected outcome, allowed observations, whether the program is defined, expected runtime check, relevant LLVM IR flags/intrinsics, and a transformation that would be invalid if the source contract were stricter. Include negative controls with deliberately invalid IR/source preconditions so the test harness verifies that its oracle distinguishes a genuine allowed optimization from an accidental behavior match.

Scenario 96A runs the integer cases with a fixed source shape, ordered effects, and a pinned LLVM pipeline. Scenario 96B checks formation and reads across logical byte views of one allocation and catches losses of bounds and origin checks. Constant folding and general allocation provenance remain further discriminators. [LLVM integer preservation](RESEARCH-SCENARIO-96A-LLVM-INTEGER-PRESERVATION.md) · [LLVM byte-view preservation](RESEARCH-SCENARIO-96B-LLVM-BYTE-VIEW-PRESERVATION.md)

## 6. Validation and falsifiers

- Differentially execute reference semantics and LLVM output at `-O0` and selected optimized levels for the same fixed-width inputs, including boundary values and generated combinations.
- Validate emitted LLVM IR with the version-pinned verifier. Treat verifier acceptance as structural validity, not semantic correspondence.
- Use Alive2 or an equivalent translation-validation tool for selected IR transformations, while recording the modeled UB/poison semantics and scope. A proof that two IR fragments are equivalent under LLVM semantics does not prove that the frontend's IR matches LLMLang source semantics.
- Run sanitizers as bug-finding evidence only. A clean sanitizer run does not establish absence of UB or full semantic preservation.
- For memory facts, include allocation identity/provenance in the reference model where the candidate language requires it; integer-address equality alone is not a sufficient oracle.

Falsify a lowering candidate if a source-defined input produces an LLVM poison/UB execution or an observable result different from the reference contract; if an optimization removes a required error/trap/cleanup; if the compiler asserts `nsw`/`nuw`/`inbounds` without a valid proof; or if safe source can trigger an IR precondition violation. A single target success is not enough to establish portability.

## 7. Consequences for LL-020 and cross-area decisions

- LL-020 remains open: this study refines the required preservation contract but does not select LLVM, an IR subset, or a UB policy.
- RT-03/04 source semantics must specify edge-case observations before backend-specific lowering can be judged. A host CPU's behavior is not the normative contract.
- RT-07 proofs must identify the source-to-IR correspondence claim and the LLVM semantics/version assumptions. An LLVM IR verifier is not a proof that LLMLang's source evaluator and IR agree.
- RT-09/13 should record, per IR instruction/flag/intrinsic, which source proposition justifies it; unsupported source constructs remain explicit rather than silently lowered to optimistic assumptions.
- Cache and evidence identities (LL-021) must bind LLVM/compiler version, target, flags, and relevant semantic/optimization profile when they can affect artifacts or claims. The source Semantic Hash remains distinct from these action inputs.
- Memory safety, cleanup-on-failure, runtime traps, and optimizer-preserved observable effects intersect Scenarios 39, 65, 72, and 75; no one layer can settle the others.

## 8. Sources

- LLVM, [LLVM IR Undefined Behavior Manual](https://llvm.org/docs/UndefinedBehavior.html).
- LLVM, [Language Reference Manual](https://llvm.org/docs/LangRef.html), especially integer arithmetic, poison values, GEP `inbounds`, and attributes.
- Rust Reference, [Overflow](https://doc.rust-lang.org/reference/expressions/operator-expr.html#overflow), [Behavior considered undefined](https://doc.rust-lang.org/reference/behavior-considered-undefined.html), and [pointer arithmetic/provenance APIs](https://doc.rust-lang.org/std/primitive.pointer.html).
- WebAssembly Core Specification 3.0, [Numeric instructions](https://webassembly.github.io/spec/core/syntax/instructions.html#numeric-instructions), [numeric execution](https://webassembly.github.io/spec/core/exec/numerics.html), and [linear memory bounds](https://webassembly.github.io/spec/core/syntax/instructions.html#memory-instructions).
- LLMLang [Scenario 45](RESEARCH-SCENARIO-45-NUMERIC-SEMANTICS-AND-OVERFLOW.md), [Scenario 65](RESEARCH-SCENARIO-65-FATAL-FAILURE-AND-UNWINDING.md), [Scenario 72](RESEARCH-SCENARIO-72-SUM-TYPE-LAYOUT-ABI-AND-INTEROPERABILITY.md), and [LL-020](../TODO.md#ll-020--define-llvm-backend-role-and-semantic-boundary).
