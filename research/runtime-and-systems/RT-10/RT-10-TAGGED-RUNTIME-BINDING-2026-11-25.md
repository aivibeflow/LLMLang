# RT-10 native tagged values and exact runtime call bindings

**Date** 2026-11-25 · **Plan** §5.2 · **Issue** [#325](https://github.com/aivibeflow/LLMLang/issues/325)

Four GCC-built native libraries export the same machine-level `u32 → u32` call. The typed operation returns a value, a denied error or a busy error. The caller interprets each word using the declared tag and payload profile. The candidate binding separately names the immutable operation descriptor, resolved ABI, representation version, exact runtime artifact, release label and call slot.

| Provider change | Observed implication |
| --- | --- |
| Tag layout changes at the same release label and unchanged logical behavior | All 256 results agree under exact profile decoders. The old decoder refuses all 256 values in the new layout. |
| Returned value changes at the same release and layout | Eighty-six inputs return a different value. Earlier version metadata and calling convention remain equal. |
| Release label changes with the same tagged semantics | Exact selected runtime bytes and release identity change. All decoded observations remain equal. |
| Exact carrier is paired with another approved runtime's bytes or an incorrect claimed release | The scoped admission refuses the substitution before issuing the semantic call. |

All 2,048 native corpus calls agree with a separate arithmetic and typed-result oracle. Two optimization levels each verify 16 requested and supplied provider pairs. The four exact same-provider pairs per level pass. The other pairs are refused. Independent field controls exercise operation identity, ABI, encoding, release and slot. A separate check detects an exact runtime file whose loaded release is different from the caller's supplied manifest.

A runtime candidate can retain stable operation identity while binding each call to its own exact implementation and runtime profile. A machine-level ABI fixes the call boundary and leaves typed interpretation to the declared representation. An explicit compatibility claim may compare observed values across versions and layouts. This fixture establishes agreement for a finite corpus over trusted local libraries. Live mutation races, constructors at dynamic load, signed admission, more value families, formal ABI lowering and production runtime versioning remain open.

Reproduce with GCC 14.2.0 and Python 3.12.14 on x86-64 Linux.

```bash
study=research/runtime-and-systems/RT-10/TAGGED-RUNTIME-BINDING-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two independent native builds reproduced exact artifact hashes and all admission outcomes.
