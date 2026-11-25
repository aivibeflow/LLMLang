# RT-13 — Guarded division specialization and compatible fallback

- **Date** — 2026-11-25
- **Tracking** — [PLAN §6.4](../../../PLAN.md#64-implementation-discovery-selection-and-optimization) · [#331](https://github.com/aivibeflow/LLMLang/issues/331)
- **Status** — Checked in Lean and independent native compiler profiles

## Question and candidate rule

When can a specialized implementation share the source meaning of a general operation? The fixture divides two unsigned 64-bit words. A zero divisor returns an error and leaves the output slot unchanged. The general route computes the quotient. When the specialization is enabled, its receipt is checked, and the exact divisor equals two raised to the selected shift count, the specialized route shifts the numerator right. Other nonzero inputs take the general route. [Evidence-gated fallback](RT-13-IMPLEMENTATION-FALLBACK-2026-11-25.md) · [Wide division capability](RT-13-WIDE-DIVISION-CAPABILITY-2026-11-25.md)

The native code derives the proposed exponent with a trailing-zero builtin after rejecting zero. It checks the exact divisor before shifting. The proof abstracts the candidate exponent and receipt as inputs and checks that the guarded computation equals the reference division for every natural input. The native runner separately checks unsigned bounds, typed error, written slot and actual route selection.

```mermaid
flowchart LR
    Q["Division request"] --> Z["Check zero divisor"]
    Z --> G["Check route evidence and exact power-of-two divisor"]
    G -->|passes| S["Use right shift"]
    G -->|fails| D["Use general division"]
    S --> V["Check result against the same source contract"]
    D --> V
```

## Results

Lean checks the guarded rule and a concrete counterexample to removing the equality gate. GCC and Clang at O0 and O3 match all 14,076 observations per profile, giving 56,304 native observations. Test inputs include 64-bit boundaries, every in-range power-of-two divisor, neighboring divisors, seeded random pairs and all combinations of route enablement and checked, absent or stale receipt state. Zero-divisor cases preserve the anchored slot. The native guard also keeps valid power-of-two inputs on the general route if specialization is disabled or evidence is absent or stale. [Evidence ledger](GUARDED-SPECIALIZATION-01/evidence.json)

Removing the divisor check changes 1,506 results in one otherwise matched profile. For numerator 63, divisor 6 and a checked enabled route, the correct quotient is 10. The unchecked shift returns 31. The mutation still guards zero and uses a defined count for the tested nonzero divisors. The result isolates a semantic error caused by an insufficient specialization condition.

## Limits

This experiment separates an input guard, artifact eligibility and a shared observation contract. The Lean theorem establishes the mathematical rule. The native matrix provides finite evidence for the selected builtin and emitted implementations. CPU feature selection, concurrent materialization, exact attestation producers, unspecialized implementation absence and production multi-version policy remain open.

## Reproduction

Run from the repository root with CPython 3.12.14, Lean 4.36.0, GCC 14.2.0 and Clang 19.1.7 on x86-64 Linux. The runner checks and records Lean's axiom report and compiles the native artifacts in temporary storage. [Lean model](GUARDED-SPECIALIZATION-01/Specialization.lean) · [Runner](GUARDED-SPECIALIZATION-01/run.py)

```sh
set -eu
dir=research/compiler-and-translation/RT-13/GUARDED-SPECIALIZATION-01
observed=$(mktemp)
trap 'rm -f "$observed"' EXIT
python3 -B "$dir/run.py" > "$observed"
cmp "$dir/evidence.json" "$observed"
```
