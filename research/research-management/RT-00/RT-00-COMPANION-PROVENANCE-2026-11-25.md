# RT-00 companion report provenance for evidence without embedded metadata

The [prior census](RT-00-EXACT-LEDGER-METADATA-2026-11-25.md) found 69 exact-name evidence ledgers without a recognized tool version, artifact fingerprint or executing-host field. This check scans the Markdown/MDX files in each fixture directory and its immediate parent at `7d407636c4a06d1b601376bc66ea96d5a26e0b8f` on `research/all`. A companion must have a local Markdown link that resolves to the exact ledger path. The [audit ledger](COMPANION-PROVENANCE-01/evidence.json) preserves each recognized path, Git blob, link line and reviewed metadata statement. [#284](https://github.com/aivibeflow/LLMLang/issues/284)

| Disposition | Count |
| --- | ---: |
| Nearby Markdown/MDX files scanned | 712 |
| Reports with an exact local ledger link | 58 |
| Ledgers covered by those reports | 57 |
| Ledgers with a versioned replay tool in a companion | 56 |
| Ledgers with a patch-specific version for at least one replay tool | 52 |
| Ledgers with tool and host information in a companion | 20 |
| Linked ledger without a versioned replay tool | 1 |
| Ledgers without a direct link in the scanned directories | 12 |

The report for the RT-37 target-closure crosswalk gives a Python command and records the reuse of seven committed ledgers. Its replay-tool version remains unspecified in that report. The RT-35 channel-cost report links the ANN ledger as nearby evidence, while its timing host statement applies to its own timing fixture. The ANN study's own companion supplies its tool versions. The audit also preserves Windows COFF as the cross-build subject and Linux as the documented build host. These decisions keep target or cited-study context from being assigned to the wrong execution.

The scanned links and statements were read at their exact archived Git blobs through GitHub's Git data API. A relative-link control distinguished the intended file from another fixture's same-named ledger and from an external URL. Replay instructions and reported execution environments are retained as written. The counts do not establish binary provenance, a complete machine configuration or an original execution attestation. Links from farther-away reports and non-inline Markdown forms are outside the scanned scope. The [local runner](COMPANION-PROVENANCE-01/run.mjs) reproduces the scoped link and line checks. The shell was offline during this study, so the local invocation remains unchecked.

```sh
fixture=research/research-management/RT-00/COMPANION-PROVENANCE-01
out=$(mktemp)
node "$fixture/run.mjs" > "$out" && cmp "$fixture/evidence.json" "$out"
```
