# RT-12 evidence for opaque implementation artifacts

Two stripped C implementations pass the same seven-input published sample at both optimization levels. The complete 65-input fixture domain distinguishes them. One variant differs only at input 17. A sample receipt supports the observations it covers, and its scope must be checked before a claim is admitted.

## Evidence boundary

| Evidence | Claim it supports |
| --- | --- |
| Exact artifact digest | Identifies the delivered bytes. |
| Typed public contract and observation profile | Specifies the permitted inputs, result and observed effects. |
| Verified publisher or build statement | Can establish who made a specific claim under a policy. Its signature does not establish implementation behavior. |
| Exact finite receipt | Supports observed outcomes for the listed inputs, artifact, contract, target, toolchain and observation profile. |
| Checked proof or refinement evidence | Can support the property and assumptions its proof establishes. The verifier still needs correspondence to the delivered artifact and environment. |

Packaging an executable alongside a public contract permits inspection and bounded execution tests even when consumers receive no source. Source-level implementation claims, correspondence of source to executable, unobserved behaviors and platform-wide claims require their own evidence. [Library layer model](RT-12-PACKAGE-AND-LIBRARY-CONTRACTS-2026-11-25.md) · [Opaque provider compatibility](../../language-design/RT-04/RT-04-OPAQUE-PROVIDER-COMPATIBILITY-2026-11-25.md)

## Native observations

The fixture compiles source and a seeded variant with GCC at `-O0` and `-O3`. The observer receives the stripped executable and supplies integer inputs through standard input. The contract covers integers from −32 to 32 and specifies the exact result line. Two additional inputs test the outside-domain indication. The fixture archives its source so the result is reproducible.

| Check | Outcome across four profiles |
| --- | --- |
| Seven published inputs | All 28 observations match. Each receipt admits its seven-input scope. |
| Complete finite domain | Two reference profiles match every observation. Both changed profiles disagree at 17. |
| Outside-domain controls | All eight observations match the expected refusal. |
| Receipt substituted across artifact, contract, target, toolchain or observation profile | Refused in both optimization levels. |
| Seven-input receipt reused for the full domain | Refused for every profile. |

The complete finite check covers only the specified input set, standard-output observations and tested execution profile. It establishes neither source semantics nor unobserved timing, concurrency, state or effects. Production use of opaque receipts requires a trusted issuer, explicit scope and replay or independent proof appropriate to the consumer's obligations.

## Reproduce

Use Linux x86-64, CPython 3.12.14 and GCC 14.2.0-19. Runs with Python hash seeds 37 and 71 reproduce SHA-256 `0b95602bc280807acd8d36755fb8b28c59462248dbca135892f2afda7dd0c8db`. [Evidence ledger](OPAQUE-EVIDENCE-01/evidence.json)

```sh
LC_ALL=C PYTHONHASHSEED=37 PYTHONDONTWRITEBYTECODE=1 \
  python research/packages-and-ecosystem/RT-12/OPAQUE-EVIDENCE-01/check.py \
  --cc /path/to/gcc > /tmp/rt12-opaque-evidence.json
```
