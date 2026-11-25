# RT-32 — Admitted SPG-to-Lean profiles and obligation corpus

The evidence covers several small profiles that use distinct admission rules. This study replays six exact fixtures and records which deterministic mappings, proof obligations, and rejection controls each profile supports. It applies to [PLAN §2.4](../../../PLAN.md#24-verified-spg-to-lean-pipeline-rt-32) and [#296](https://github.com/aivibeflow/LLMLang/issues/296).

| Profile | Admitted input and generated proof interface |
| --- | --- |
| Call-free effectful conditionals | Unary mathematical integer function, typed arithmetic, equality, ordered emitted events and lazy arms. Decode the structured SPG body and emit the shallow observation function, structured-source correspondence, and exact branch observations. [Conditional correspondence](RT-32-CONDITIONAL-EMBEDDING-CORRESPONDENCE-2026-11-25.md) |
| Natural countdown | Exact typed loop fixture with a guard, update, invariant, trace and natural measure. Emit initialization, guarded preservation, decrease and exit obligations before composing total correctness. The loop fixture supplies a verification IR and leaves general SPG extraction open. [Countdown obligations](RT-32-COUNTDOWN-LOOP-OBLIGATIONS-2026-11-24.md) |
| Defined mutual recursion | Exact keyed or structural two-member SPG group. Resolve each internal call position to its group member, reduce a natural measure, and check the declared base and step results. [Mutual termination](RT-32-GENERATED-MUTUAL-TERMINATION-2026-11-24.md) |
| Ordered effects in mutual recursion | Extend the recursion fixture with entered/base/exited trace events. Check the exact finite trace contract separately from the unbounded natural recursion equations. [Mutual effects](RT-32-MUTUAL-RECURSIVE-EFFECTS-2026-11-24.md) |
| Unary modular calls | Use exact operation selection or implementation pin, versioned argument and result roles, and ordered trace requirements. Emit a conditional caller theorem, a provider-conformance theorem and a closure theorem for the exact bound provider. [Generated contracts](RT-32-GENERATED-CALL-CONTRACTS-2026-11-24.md) |
| Compiled proof admission | Bind a compiled module bundle to exact requested subjects, theorem type, imported context, approved axioms, toolchain and issuer. It supplies a receipt for a checked claim. [Compiled claim admission](RT-32-COMPILED-CLAIM-ADMISSION-2026-11-24.md) |

A coherent verification profile must declare its integer domain, effects and control semantics before generation. Admission needs the exact versioned implementation, contracts, reference table, and profile-specific invariants or measure. A theorem belongs to the emitted exact subject. The conditional call profile proves ordered traces, and a checked arithmetic result would require its own requested property. Profiles that use source fixtures or partial decoding retain their recorded source-correspondence premise.

## Positive and adversarial controls

The fresh replay reproduces six evidence ledgers byte for byte. It includes 12 structured conditional proofs and 168 ground observations, two loop proofs, both mutual encodings in each recursive fixture, seven closed caller claims and two admitted compiled receipts. These counts refer to separate experiments with different claims.

| Requested adversarial case | Observed result |
| --- | --- |
| Incorrect implementation | Reversed provider effects block provider conformance. A changed recursive base case fails its agreement theorem. |
| Weakened imported contract | The widened trace assumption cannot establish the stricter caller theorem. |
| Missing invariant | The countdown generator refuses the input before creating proof obligations. |
| Invalid termination measure | The zero-decrease loop fails decrease and preservation. The recursive zero-stride control also fails. |
| Mismatched translation | Lean rejects the reversed condition effects and eager evaluation of the unused arm. |
| Stale callee proof | The generated stale provider proof fails, as does replay of its compiled receipt at the rebound request. |
| Unsupported effect | The additional `foreign-effect` structured token is rejected before lowering, as checked by Lean. |

This corpus provides shared acceptance and refusal evidence for the named profiles. It leaves their general union, recursive/call effects across profiles, complete parser and generator correspondence, richer environmental contracts and production issuer policy open. [DEP-181 and DEP-182](../../research-management/RESEARCH-DEPENDENCY-MAP.md#3-directed-dependency-register)

## Reproduce

Use Git 2.56.1, CPython 3.12.14, OpenSSL 3.5.7 with Ed25519 support and Lean 4.36.0 at `611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9`, available through Elan. Run from the repository root with archive commit `95339a98c50b914d9ba7ce12fed37ba113d09cc9` and its ancestors available. The [ledger](CORE-OBLIGATION-CORPUS-01/evidence.json) records exact archive identities and each refusal route.

```sh
set -eu
fixture=research/formal-verification/RT-32/CORE-OBLIGATION-CORPUS-01
out=$(mktemp)
trap 'rm -f "$out"' EXIT
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > "$out"
cmp "$fixture/evidence.json" "$out"
```
