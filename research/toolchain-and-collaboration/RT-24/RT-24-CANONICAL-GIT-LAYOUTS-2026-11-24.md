# RT-24 Canonical Git export with packed declarations and per-slot files

Twenty-four different Git trees imported to the same six semantic selections. Each of two canonical export layouts produced one exact output tree across all input variants and re-imported to the original semantic root. The packed layout used fewer baseline files and bytes. Per-slot files rewrote fewer bytes for the isolated edit, while changing or replacing more blobs for a provider update and an occurrence rename.

## Import and export boundary

The replay uses the existing closed-inventory Git importer, typed declaration normalization, immutable value storage and independent graph check. The input includes a type, contract, effect, provider and two exact call sites. Two selection slots point to the same provider value. Across 24 inputs, formatting, escaping, source paths, file grouping, declaration order, reference order and call-site target order vary. The fixture preserves the order of the provider's event payload.

Both exporters reconstruct declarations from the imported normalized values. One packs rows into a single objects file. The other uses one file per selected occurrence, named by a domain-specific digest of the slot label. That mapping gives a case-neutral ASCII path even for the fixture's Unicode label with a slash. Both emit a manifest and build a private Git program tree. A fresh import must reproduce every slot-to-value selection and the exact semantic root, and a second export must reproduce the same files byte for byte.

| Layout | Baseline files | Baseline bytes |
| --- | ---: | ---: |
| Packed | 2 | 2,717 |
| Per-slot | 7 | 3,220 |

| Source change | Packed added or changed blobs / bytes | Per-slot added or changed blobs / bytes | Per-slot removed blobs |
| --- | ---: | ---: | ---: |
| Edit only the effect declaration | 1 / 2,665 | 1 / 199 | 0 |
| Update the provider value across its two occurrences and retarget the caller | 1 / 2,668 | 3 / 1,915 | 0 |
| Rename one occurrence label | 1 / 2,673 | 2 / 1,664 | 1 |
| Reverse the ordered provider payload and rebind exact calls | 1 / 2,668 | 3 / 1,915 | 0 |

Each content or selection edit changes the semantic root. The measurements count uncompressed replacement blob bytes in this fixture. Git pack compression, plain-text merge behavior and repository-scale storage costs remain separate measurements.

The five rejected controls use an unknown manifest version, unknown declaration schema, duplicate slot, missing listed source file and unavailable exact callee. Both exports preserve matching aliases as separate selections. The experiment compares physical packaging within the current candidate slot model. Broader syntax normalization, recurring dependencies, portable name policies, the stable-identity decision and production schema remain open. [RT-24 candidate contract](RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md) · [Identity alternatives](RT-24-IDENTITY-DECISION-MATRIX.md).

## Reproduction

Use Git 2.52.0 and CPython 3.12.14. [Exact source trees, canonical blobs and change counts](canonical-git-layouts/results.json).

```sh
python3 -B research/toolchain-and-collaboration/RT-24/canonical-git-layouts/run.py \
  --output /tmp/llmlang-canonical-git-layouts.json
cmp /tmp/llmlang-canonical-git-layouts.json \
  research/toolchain-and-collaboration/RT-24/canonical-git-layouts/results.json
```
