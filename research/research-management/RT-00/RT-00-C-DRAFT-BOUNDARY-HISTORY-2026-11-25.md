# RT-00 C — Historical publication boundaries under draft/

## Question and method

When did `draft/` become the candidate specification, and which later draft changes amended the accepted architecture decision? The [direct citation audit](RT-00-C-DRAFT-CITATION-RESEARCH-ALL-AUDIT-2026-11-25.md) covers one current snapshot. This review examines every first-parent tree where draft content changed in the ancestry of `9196d810463a4f978c327c1065a81a3db9c9ecf9` on `research/all`. This is the branch's publication sequence.

I examined the 21 draft-affecting trees and relevant diffs, including repository layout changes, new example sketches and changes to proposal and decision text. For each accepted-decision version I compared the exact decision, boundaries, consequences and reconsideration text. The table and ledger show the sequence and distinguish status introductions from link-only updates. A diagram would repeat the sequence. [Tree and decision ledger](RT-00-C-DRAFT-BOUNDARY-HISTORY-2026-11-25.json)

## Findings

| First-parent publication | Effect on the boundary |
|---|---|
| `bf9604a` through `790edf3` | `draft/` was a staging location for project material and received two research reports. Its early path usage supplies historical context before the explicit directory boundary. |
| `1a0a5cf`, then `66dc7ea` through `47c30f1` | Research moved to `research/`. Draft accumulated three candidate examples, the proposed glossary and an index explicitly assigning research its exploratory role. |
| `e9ed986` then `9c7f621` | The first tree temporarily removed every draft path, and the next draft-affecting tree restored the layout. The restored draft has the same tree object as the preceding `47c30f1` draft. |
| `d1dbf87` then `27d3041` | RT-20 terminology enters the proposed glossary. The following change explicitly publishes the accepted decision about immutable component versions and same-toolchain build compatibility. |
| `9dbb830` through `c9cb445` | The glossary develops candidate terms and supporting research links. The three changes to the accepted decision file add a related proposal note or update link paths. The decision, boundary, consequence and reconsideration text has the same digest across all four file versions. |

The glossary consistently identifies itself as a terminology proposal across its published versions. The candidate examples retain their status as sketches. The early staging history and the exact restoration show why historical path names alone give weak evidence about a document's status. Once the candidate boundary was explicit, the observed transfers were a recorded acceptance, proposal additions or traceability edits. This finding applies to the published draft trees on the pinned history. The technical validity of the underlying research claims and independent quality review remain separate obligations. [Accepted decision](../../../draft/ARCHITECTURE-DECISIONS.md) · [Proposed glossary](../../../draft/GLOSSARY.md) · [Stage 0.2 tracking](https://github.com/aivibeflow/LLMLang/issues/285)

## Reproduction

Use Git 2.56.1 and CPython 3.12.14 with the pinned commits. The ledger retains the exact revision identities, draft file counts and decision blobs. The decision digests cover the UTF-8 text after the `Decision` heading up to the optional `Related research` heading, with leading and trailing whitespace stripped.

```bash
git log --first-parent --reverse --format='%H %s' 9196d81 -- draft
git diff --exit-code 47c30f1 9c7f621 -- draft
git log --first-parent -p 9196d81 -- draft/ARCHITECTURE-DECISIONS.md
git diff 27d3041 9196d81 -- draft/ARCHITECTURE-DECISIONS.md
```
