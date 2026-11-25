# RT-34 typed resource contracts and exact kernel evidence

**Date** 2026-11-25 · **Plan** §2.0, CX-01–03 · **Issue** [#412](https://github.com/aivibeflow/LLMLang/issues/412)

This candidate Contract IR defines one versioned resource profile for successful selection and materialization. The size inputs are the source length `n` and selected count `k`, with `k ≤ n` and an explicit minimum for `n`. Two typed metrics use separate units and affine bounds over those inputs. Work is a cumulative step count. Peak live storage is a maximum in entries. Both are upper bounds over the declared outcome and size domain.

The abstract subject charges `1 + 2n + k` work steps and `k` live entries. The runner translates each metric claim to a Lean proposition over natural numbers with explicit size assumptions. It checks the exact two-variable bounds and the safe weaker envelopes `1 + 3n` and `n`. Eight propositions pass the kernel and audit. Two propositions which omit a necessary term are refused by the solver. A separate finite model checks the exact expressions and envelopes over 2,145 admissible size pairs.

| Boundary | Checked result |
| --- | --- |
| Profile, aggregation and outcome | A different profile version, an expected-cost request and a timeout outcome are outside this schema. |
| Size and metric units | Unrecognized size measures or variables, Boolean sizes, swapped units and negative coefficients are refused. |
| Serialization | Changing map insertion order preserves the contract digest. |
| Receipt identity | Substituting metric, exact subject, size assumptions, checker, generated proof, contract digest, valid restricted domain, or a different proved envelope refuses the original receipt. |
| Receipt trust | A checked receipt without authorization is refused. Changing its kernel transcript hash invalidates its authorization. |

The candidate uses different identities for a typed resource contract and for a checked evidence receipt. The receipt binds the contract, metric, exact subject, version and binary digest of the invoked Lean executable, axiom audit policy, generated proposition and proof, and the exact scoped assumptions. Its full digest also binds the kernel log. The authority fixture uses an externally supplied allowlist of receipt identities.

The model checks finite typed affine input and unbounded symbolic bounds for one abstract selection subject. Canonical SPG integration, source extraction, general size relations, multi-profile comparisons, checker installation trust and authorized issuers remain open. Metrics for cumulative work and peak storage carry separate proofs. Native implementation correspondence requires further evidence.

Reproduce with the direct Lean 4.36.0 binary and Python from the repository root.

```bash
study=research/formal-verification/RT-34/RESOURCE-CONTRACT-IR-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two fresh runs produced byte-identical evidence. The audit permits `propext` and `Quot.sound` for successful generated proofs.
