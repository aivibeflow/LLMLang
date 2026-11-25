# RT-00 tool and host fields in the exact-name evidence delta

The [exact-name provenance refresh](RT-00-EXACT-LEDGER-REFRESH-2026-11-25.md) found 207 added `evidence.json` files without a matched flat source field. For those files this check records which selected fields supply tool version strings, artifact fingerprints or executing-host details. All 207 inputs were read from their exact Git blobs at `7d407636c4a06d1b601376bc66ea96d5a26e0b8f` on `research/all`. The [ledger](EXACT-LEDGER-METADATA-01/evidence.json) retains each recognized field and its original value alongside the artifact path and Git blob. [#284](https://github.com/aivibeflow/LLMLang/issues/284)

| Recorded information | Ledgers |
| --- | ---: |
| Tool version string | 133 |
| Tool or runtime artifact SHA-256 string | 15 |
| Executing-host field | 22 |
| Tool identity and host field | 17 |
| Tool version with no selected host field | 116 |
| No recognized field under this check | 69 |

These rows overlap. Every artifact fingerprint in the sample occurs in a ledger that also supplies a version. Host fields include kernel release, machine architecture, filesystem or CPU name where the producer's field identifies the actual execution host. A ledger with both types of data can still lack a full environment specification. Emulated targets, supported runtime profiles and arrays of compiler refusals do not supply an execution host. Controls confirmed that such fields do not count, and that a compiler version, artifact digest and explicit host record do. Reversing the order of the inputs produced identical evidence.

This is a metadata census of the enumerated fields. It leaves adjacent reports, other nested schemas, downloaded tool bytes and original run environments outside the checked scope. Exact field values were read through GitHub's Git data API. The [local runner](EXACT-LEDGER-METADATA-01/run.mjs) shares the field logic and verifies every selection against Git. A subsequent local invocation with Node.js 24.22.3 and Git 2.56.1 on Linux 6.18.57 x86-64 reproduced the committed JSON byte for byte.

```sh
fixture=research/research-management/RT-00/EXACT-LEDGER-METADATA-01
out=$(mktemp)
node "$fixture/run.mjs" > "$out" && cmp "$fixture/evidence.json" "$out"
```
