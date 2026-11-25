# Conditional FFI caller proof and exact observation scope

[GitHub #329](https://github.com/aivibeflow/LLMLang/issues/329) · 2026-11-25

The verified caller decodes an external checked-add reply into a value, overflow with retained output, or an unknown status and its raw output. It assumes a live writable output slot and the external provider's two behavioral clauses. A successful computation supplies the exact sum or pass-through value. Overflow supplies its explicit status and preserves the prior slot.

Lean checks successful decoding, overflow preservation, retention of unknown raw replies, and an ABI-shaped reply that violates the expected overflow result. All four theorems are axiom-free. The premises describe external behavior. The audit keeps this source-level result conditional on those premises. [External trust model](../../formal-verification/RT-36/RT-36-FORMAL-VERIFICATION-ASSUMPTIONS-AND-TRUST.md)

The runner independently rebuilds and replays the six-language export fixture, including both observed compatible revisions and the same-ABI behavior control. All 1,440 observations reproduce the original exact ledger. A candidate receipt binds the public contract, selected ELF, ABI, target, native environment, observation and caller profile, and records the exact proof and native trace identities. The environment includes the kernel, loaded libc and loader digests. The fixture supplies the verified-receipt inventory.

| Control family | Outcome |
| --- | --- |
| Exact original and independently checked replacement | Conditional on the provider premise |
| Old receipt after replacement, changed ABI or profile, changed contract or observation scope | Unknown due to stale scope |
| Exact receipt with observed semantic failure | Observed contradiction |
| Missing, unverified or incomplete observation | Distinct unknown reason |
| Different proof subject | Unknown proof scope |
| Missing caller storage premise | Caller obligation remains open |

All 15 controls match their stated dispositions. A changed versioned library with the same ABI requires fresh observations. An incompatible witnessed behavior remains a contradiction for its exact scope. These tests validate one integration of native evidence and conditional proof. Source-to-binary correspondence, supplier authentication, non-Linux loaders and production receipt verification remain open. [Six-language export results](RT-13-FFI-SIX-LANGUAGE-EXPORT-2026-11-25.md)

## Replay

Use Lean 4.36.0 and the tool and runtime versions from the native fixture.

```sh
fixture=research/compiler-and-translation/RT-13/FFI-CONDITIONAL-RECEIPTS-01
scratch=$(mktemp -d)
python "$fixture/run.py" --go /path/to/go1.27.4 --go-cache "$scratch/go-cache" \
  --output "$scratch/evidence.json"
cmp "$fixture/evidence.json" "$scratch/evidence.json"
```

Two full replays produced identical [evidence ledgers](FFI-CONDITIONAL-RECEIPTS-01/evidence.json).
