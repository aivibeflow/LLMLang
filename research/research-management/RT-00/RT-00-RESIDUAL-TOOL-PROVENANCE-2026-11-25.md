# RT-00 remaining version provenance for 13 evidence ledgers

This audit follows the 13 ledgers without a versioned tool under the [nearby exact-link check](RT-00-COMPANION-PROVENANCE-2026-11-25.md). It uses the same pinned `research/all` tree, `7d407636c4a06d1b601376bc66ea96d5a26e0b8f`. It checks the branch plan, exact fixture entry points, nested result fields, and report commands that name the fixture directory. The [ledger](RESIDUAL-TOOL-PROVENANCE-01/evidence.json) records the exact Git blobs, field paths and report line references. [#284](https://github.com/aivibeflow/LLMLang/issues/284)

| Disposition | Count |
| --- | ---: |
| Additional version found in a field specific to the producer | 8 |
| Version found in a report that names the fixture in its reproduction command | 4 |
| Checked fixture without a version in its source records | 1 |

The eight embedded matches include four Rust studies that use the field `rust`, a Rust and Go study that uses `toolchains`, the resource-contract IR checker, native compiler profiles in the algebraic encoding rows, and the C/Rust action descriptors in the cross-language receipt study. The runner sources confirm the selected fields are tool version outputs. Three command-linked reports specify Lean 4.36.0 for their proof checks, and the resumable execution report specifies CPython 3.12.14. Preserve the partial nature of these recipes. For example, the package-delivery report also names GCC, GNU readelf and Python without versions.

The RT-37 target-closure crosswalk calls `python -B` and reads seven committed evidence ledgers. The checked report and fixture records give no version for that Python execution. Tool identities for the referenced firmware studies apply to their own evidence. The pinned plan does not mention any of the 13 fixture identifiers literally. A control substituted a different command line and the verifier rejected the association. Reversing the manifest order produced the same audit ledger.

The checks used exact GitHub Git data responses. The [local reproduction command](RESIDUAL-TOOL-PROVENANCE-01/run.mjs) uses the same comparison logic. A subsequent local run with Node.js 24.22.3 and Git 2.56.1 on Linux 6.18.57 x86-64 reproduced the committed JSON byte for byte.

```sh
fixture=research/research-management/RT-00/RESIDUAL-TOOL-PROVENANCE-01
out=$(mktemp)
node "$fixture/run.mjs" > "$out" && cmp "$fixture/evidence.json" "$out"
```
