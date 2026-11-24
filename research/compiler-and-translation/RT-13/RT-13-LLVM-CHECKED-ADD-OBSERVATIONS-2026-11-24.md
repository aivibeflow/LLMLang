# Whole-domain observation checks for LLVM checked addition

- **Date:** 2026-11-24
- **Research:** RT-03, RT-07, RT-09 and RT-13; PLAN §2.5 and §6.3
- **Baseline:** `af1f0cfe121a8ee8ff0a42fe15aa9f4bf3c967f4`
- **Evidence:** Exact O0 and O3 LLVM artifacts, independent solver replays and six native counterexample checks

For the signed checked-add program from [Scenario 96A](RESEARCH-SCENARIO-96A-LLVM-INTEGER-PRESERVATION.md), the admitted LLVM artifacts preserve status, output-slot stores and ordered callback events for every input in the bit-vector model at O0 and O3. Both solvers rule out a mismatch over all bit patterns of the two operands and the ABI enable argument. Three LLVM-verifier-accepted controls disagree with the source model at both optimization levels.

## Exact artifact and source models

The replay reads the real textual IR after `verify,default<O0>,verify` or `verify,default<O3>,verify`. The reader follows both arms of each branch, selects `phi` inputs by predecessor and records the status, ordered callback payloads and stores through `%out` on each exit. It admits the observed signed-overflow intrinsic, selected-operand and plain addition instructions, and the required control-flow subset. Unexpected syntax or arithmetic flags leave the artifact unsupported. Both solvers check that the modeled exit guards partition the input space.

The source formula sign-extends both signed operands to 33 bits so their mathematical sum fits exactly. It tests that sum against the signed 32-bit endpoints. The LLVM intrinsic model instead takes the 32-bit sum and tests whether the input signs agree while the result sign differs. On source overflow the expected outcome has status `overflow`, one callback and zero stores. The successful and skipped branches emit two callbacks and store the returned bits. The ABI treats zero as disabled and every other enable bit pattern as enabled.

| LLVM artifact | Full mismatch query at O0 and O3 | Distinguishing native observation |
| --- | --- | --- |
| Preserving lowering | `unsat` | Existing native corpus covers both optimization levels. |
| Discard overflow branch | `sat` | For `2147483647 + 1`, status becomes `ok`, bits `0x80000000` reach the slot and a second event is emitted. |
| Reverse success effects | `sat` | With operands `(2, 3)` and the operation disabled, the events are `[3, 2]` instead of `[2, 3]`. The status-and-stores query is `unsat`. |
| Store zero on overflow | `sat` | The overflow status and callback match, while the output sentinel changes to zero. The status-and-effects query is `unsat`. |

A fourth control adds an unmodeled `add nsw` to valid O0 IR. The reader reports `unsupported`. This checks the boundary for LLVM promises whose poison semantics are outside this model.

## Reproduce and scope

Use LLVM 19.1.7, GCC 14.2.0, Z3 4.13.3, cvc5 1.4.2 (`282d5e0`) and Python 3.12.14 on Linux x86-64. The [replay](../PROTOTYPES/LLVM-PRESERVATION-01/checked_add_replay.py) checks 38 exact QF_BV queries on each solver and compiles six native controls. The [ledger](../PROTOTYPES/LLVM-PRESERVATION-01/checked-add-results.json) provides the exact IR and solver-input hashes, path counts, verdicts and concrete observations.

```sh
fixture=research/compiler-and-translation/PROTOTYPES/LLVM-PRESERVATION-01
results=$(mktemp)
python3 -B "$fixture/checked_add_replay.py" --output "$results"
cmp "$fixture/checked-add-results.json" "$results"
```

The bit-vector claim assumes defined scalar inputs, an aligned and writable output slot, and a returning callback that records its payload without accessing that slot. The reader and both formulas remain part of the trust boundary. Independent solver agreement checks the formulas, and native controls test concrete observations. General LLVM semantics, proof-certificate checking, source-to-SPG binding for this program, and whole-domain correspondence at the native ABI are separate obligations.

The [certificate follow-up](RT-13-LLVM-CHECKED-ADD-CPC-BINDING-2026-11-24.md) generates and checks CPC refutations bound to the complete O0 and O3 mismatch formulas in the Logos runtime.
