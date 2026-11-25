# RT-24 textual SPG subset and pinned clean-clone reconstruction

A source-first Git representation should reconstruct the exact selected graph without a previous semantic database, cache or local index. This study selects a small candidate subset containing a typed entry point, one exact dependency and observable checked arithmetic failure. It checks canonical textual import/export in native SHA-1 and SHA-256 Git repositories. The subset is sufficient to distinguish source, dependency and graph identity in this experiment.

## Textual fixture

The required inventory contains three regular tracked files.

| Path | Exact meaning |
|---|---|
| `src/entry.llm` | One import and an exact typed direct call over signed 64-bit input and explicit `Result<I64, Overflow>` |
| `vendor/math.llm` | One directly selected dependency with the declared signature and a checked addition |
| `llmlang-manifest.json` | Profile, exact byte digests, typed dependency declaration and selected semantic root |

The fixture's source spelling is illustrative.

```text
import math.inc
fn entry(x: I64) -> Result<I64, Overflow> = math.inc(x)
```

The immutable dependency lock names `math.inc`, a regular tracked source path, the source's exact SHA-256 and the typed contract/profile `checked-add-i64/1`. A changed implementation requires fresh typed callee and caller addresses because this reference is direct. The raw caller file can stay byte-identical. The selected root and authoritative lock are recomputed from the same admitted graph. Vendoring the dependency makes its exact bytes available in a Git-only checkout. Production externals can use a separate authorized exact dependency acquisition route. Their availability and provenance are separate from resolving the lock.

```mermaid
flowchart LR
  T[Exact native Git tree] --> F[Check regular paths and closed source inventory]
  F --> L[Verify exact source hashes and dependency lock]
  L --> G[Parse typed expressions and construct exact graph]
  G --> E[Export normalized source and manifest]
  E --> R[Compare original bytes and declared root]
  R --> X[Run bounded interpreted observations]
```

The importer reads only exact Git tree blobs. It checks path mode, profile, canonical manifest, declared source hashes, lock agreement, admitted syntax, graph root and identical export. Reconstructible stores, indices and result caches are not inputs to this fixture. A readable file gives source provenance and can be a tool input while program meaning is determined by the admitted typed graph.

## Checked cases

The runner creates 28 separate temporary native histories. It clones via Git transport without local object sharing, removes the remote and checks a clean checkout and exact selected commit. Four positive cases cross two checked-add versions with two Git object formats. Corresponding SHA-1 and SHA-256 clones yield identical graphs, interpreted outputs and canonical source exports for each version.

For each positive clone, seven signed inputs include minimum and maximum values and the upper boundary at which the two bodies differ. All 28 observations match the independent integer range oracle. A provider-only edit changes the called value and selected root while keeping the original entry source stable. A signed overflow result remains distinct from a normal return.

The 24 refusal cases cover six ordinary source-integrity faults, each across both versions and formats. The faults omit a required file, change its mode while keeping bytes, retain a stale source pin, alter the dependency pin, change to an unsupported exact call even with a current file digest, or supply the wrong semantic root. Exact canonical import and export refuse every variant.

An embedded text dependency keeps this profile reconstructible without registry IO. A manifest-only external reference can reduce the checkout but requires independently available exact bytes. The [native Gitlink comparison](RT-24-PINNED-GITLINK-RECONSTRUCTION-2026-11-25.md) finds seven exact available dependency cases among 13. The [typed CLI clean-clone fixture](RT-24-CLEAN-CLONE-CLI-2026-11-25.md) supplies 272 native execution observations and two candidate layouts. The [mixed-version I64 merge](RT-24-VERSIONED-I64-GIT-MERGE-2026-11-25.md) checks lossless scalar representation and parent-root discipline for an additional wire profile. These are separate scopes.

## Verify and limits

The [runner](TEXTUAL-SPG-CLONE-01/check.py) and [ledger](TEXTUAL-SPG-CLONE-01/evidence.json) use CPython 3.12.14 and Git 2.56.1 on the Linux host. The fixture was claimed at `2546379f0bed8a44ef80ef40597d9c7d9ca8f16b`. Hash seeds 37 and 71 give identical observations and typed addresses. The binary status, checked source bytes and exact digests provide the claimed round trip for this closed grammar.

```bash
fixture=research/toolchain-and-collaboration/RT-24/TEXTUAL-SPG-CLONE-01
LC_ALL=C PYTHONHASHSEED=37 python3 -B "$fixture/check.py" > /tmp/llmlang-textual-spg.json
cmp "$fixture/evidence.json" /tmp/llmlang-textual-spg.json
```

General source parsing and language syntax, multi-file and cyclic dependency closures, source profiles on other filesystems, external package authority, and a selected canonical production representation remain open. This result demonstrates the subset rather than a general round-trip theorem.
