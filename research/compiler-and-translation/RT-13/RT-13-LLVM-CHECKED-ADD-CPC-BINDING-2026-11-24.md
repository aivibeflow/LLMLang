# Binding Logos certificates to exact LLVM checked-add queries

- **Date:** 2026-11-24
- **Research:** RT-07, RT-13, RT-36 and PLAN §2.5
- **Baseline:** `690ccbbb00ac2a93b5b54871f6d19a2e710eedd6`
- **Evidence:** Two exact cvc5 CPC refutations, Logos replay and four binding or proof controls

Logos returns `correct` for the CPC refutations of the exact O0 and O3 whole-observation mismatch formulas. The declaration-aware checker binds each proof to its own formula and rejects swapping the two certificates. A coherent rename of one external input still yields `correct` in standalone Logos and fails the source declaration check.

## Material checked by the parser and verdict

The [prior study](RT-13-LLVM-CHECKED-ADD-OBSERVATIONS-2026-11-24.md) checks the status, output stores and ordered callbacks of the exact Scenario 96A signed-add IR. This replay regenerates those O0 and O3 artifacts and matches the earlier IR and full mismatch-query hashes before asking cvc5 for CPC output. It removes the `unsat` line and the outer response parentheses. The CPC commands are otherwise preserved byte for byte.

The [Lean checker](../PROTOTYPES/LLVM-PRESERVATION-01/CheckedAddCertificate.lean) reads the exact SMT-LIB query. It checks one assertion and three 32-bit declarations and renders the supported operators and literals into Eunoia syntax. The Logos parser assigns constant IDs by declaration order. The source declares `a`, `b`, `enabled`, while both emitted certificates declare `enabled`, `a`, `b`. The checker first requires an exact permutation of the three names and sorts at the start of the proof, with no additional declarations in the admitted command profile. It then parses the source assertion under the checked order. Equality compares the resulting ordered assumption list to the ordinary parser's actual assumptions for the proof. The verdict runs on the exact commands from that same proof parse.

| Input | Standalone Logos verdict | Bound checker result |
| --- | --- | --- |
| O0 certificate and O0 query, 1,286 proof steps | `correct` | `correct` |
| O3 certificate and O3 query, 1,269 proof steps | `correct` | `correct` |
| Exchange O0 and O3 certificates | `correct` for either certificate's own assumptions | `assumptions-mismatch` in both directions |
| Rename the external input `a` throughout the O0 proof | `correct` | `declarations-mismatch` |
| Replace the final stated O0 conclusion `false` with `true` | `incorrect` | `incorrect` |

## Reproduce and scope

Use LLVM 19.1.7, cvc5 1.4.2 (`282d5e0c84baf49c780704c532f87ba66d8b513d`), Logos `cf18742973861b3718d04c5f25775448098ff474` and Lean 4.34.0 (`293d5d0c0c3f3dded4688b3ccd6a33939ac5102b`). The [ledger](../PROTOTYPES/LLVM-PRESERVATION-01/checked-add-certificate-results.json) records the original solver output and flat proof hashes, along with the exact formula and IR identities and checker outcomes.

```sh
fixture=research/compiler-and-translation/PROTOTYPES/LLVM-PRESERVATION-01
output=$(mktemp)
python3 -B "$fixture/checked_add_certificate_replay.py" --checkout /path/to/pinned/logos --output "$output"
cmp "$fixture/checked-add-certificate-results.json" "$output"
```

The evidence checks the compiled Logos runtime and its ordinary parser and verdict on the admitted certificate profile. The formula construction and the SMT-LIB to Eunoia rendering remain trusted transformations within the experiment. The full upstream rule proof, its axiom audit and authoritative source-to-LLVM correspondence remain separate gates. [Logos checker trust boundary](../../formal-verification/RT-07/RT-07-LOGOS-CHECKER-TRUST-BOUNDARY.md)
