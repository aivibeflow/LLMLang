# RT-00 D — External snapshot provenance audit

**Audit snapshot:** `dcbb3085bfc6fb45eaaf520ca27aef4e93a628ae`  
**Date:** 2026-11-20  
**Scope:** MCP, OCI image-spec, Alive2, and Bazel Remote Execution API snapshots under `research/references/snapshots/`; snapshot manifest, license provenance, relative-link closure, and link-only references.  
**Method:** exact local Git tree comparison, upstream GitHub commit/tree/blob verification, upstream commit signature-status checks, JSON schema reference checks, Markdown relative-link resolution, and proto import-closure review.

## 1. Executive result

The repository contains 13 snapshot/license files across four upstream repositories. Independent verification confirms:
- 4/4 upstream commit tree SHAs match the manifest;
- 13/13 upstream file blob SHAs match the manifest;
- 13/13 local snapshot file blobs match the same upstream blob SHAs;
- no missing upstream path, unmanifested local snapshot file, or content mismatch was found;
- all four upstream commits have GitHub commit-signature verification status `verified: true`.

The snapshot integrity is strong. The snapshots are not all self-contained documentation or build inputs: OCI and Alive2 have unresolved relative links, and the REAPI proto snapshot omits its import closure. These are completeness limitations, not blob-integrity failures.

## 2. Snapshot inventory

| Source | Upstream commit | Upstream tree | Local files | Upstream blobs matched | GitHub commit signature |
|---|---|---|---:|---:|---|
| MCP `modelcontextprotocol/modelcontextprotocol` | `5f5440bb26a62e2cf3440b92da5a667efa03b267` | `8957e31e8ecd6fd7f52df82d44b3827cb44cecb1` | 5 | 5/5 | Verified |
| OCI `opencontainers/image-spec` | `4feed4a6674e59d301b9294f187ac46acb2de99f` | `db49a85ed9c7cf9ea73c3e686587e9d11de3d085` | 4 | 4/4 | Verified |
| Alive2 `AliveToolkit/alive2` | `3bdd4f5e1cefa47057e93110e707acd11cfe08e4` | `00afc2cc9bf27749415d1ab1ac48750d4818a2fe` | 2 | 2/2 | Verified |
| REAPI `bazelbuild/remote-apis` | `e0c0554bfc8a37abf336c3e78070684367738e1d` | `1fc34a272f266ba16d6dd82f6ef21dac9dbdff18` | 2 | 2/2 | Verified |
| **Total** | **4 immutable commits** | **4 exact trees** | **13** | **13/13** | **4/4** |

The manifest maps each local path to the upstream repository path and Git blob SHA. Every upstream commit's tree SHA was independently compared with the manifest, then every listed upstream path/blob was compared with both the upstream tree and the current LLMLang tree.

The upstream commit signatures are verified by GitHub. The local `SNAPSHOT-MANIFEST.json` itself is not signed; its content is a repository record of the verification, not a signed provenance attestation. This distinction is already stated in the manifest's note and should be preserved.

## 3. License provenance

The 13 files include the relevant upstream license texts:
- MCP: upstream `LICENSE.md`, including the distinction between Apache-2.0 specification material and CC-BY-4.0 non-specification documentation;
- OCI: Apache-2.0 license;
- Alive2: MIT license;
- REAPI: Apache-2.0 license.

The OCI and REAPI Apache license snapshots have identical Git blob content, as expected for the same license text. The snapshot README identifies the source repositories and pinned revisions. No local license file was substituted or modified.

License inclusion establishes the copied text and its upstream location; it does not replace project-level legal review of how a future derived artifact is used.

## 4. Completeness and link closure

### 4.1 MCP

The MCP snapshot contains the selected 2026-07-28 specification pages, authorization and transport material, the schema, and the upstream license.

The JSON schema:
- parses as JSON;
- declares JSON Schema draft 2020-12;
- contains 155 top-level `$defs`;
- contains 277 local `$ref` references;
- has no unresolved local `#/$defs/...` references and no external `$ref` references.

This is a structural reference check, not a full validation of every schema definition against the official JSON Schema meta-schema. The snapshot's absolute upstream links remain external links; they are not claimed to be local copies.

### 4.2 OCI image-spec

The local snapshot contains `descriptor.md`, `manifest.md`, `image-layout.md`, and the Apache license. Link resolution finds **32 unresolved relative-link occurrences** across the three documents, pointing to seven documents not included in the snapshot:

- `media-types.md`;
- `annotations.md`;
- `image-index.md`;
- `considerations.md`;
- `conversion.md`;
- `config.md`;
- `layer.md`.

The local copies are exact upstream blobs, but this is a deliberately partial documentation snapshot, not a self-contained OCI specification copy.

### 4.3 Alive2

The local snapshot contains the upstream README and MIT license, not the Alive2 source tree or executable. The README has six unresolved relative-link occurrences: five image assets and `BugList.md`.

This snapshot is useful for prior-art orientation and attribution. It is not sufficient to reproduce Alive2 or build the tool.

### 4.4 REAPI

The local snapshot contains `remote_execution.proto` and the Apache license. The proto imports eight other files. Only one imported file, `build/bazel/semver/semver.proto`, exists in the pinned `remote-apis` upstream tree; it is not copied locally. The other seven imports are Google API/Protobuf definitions outside that repository:
- `google/api/annotations.proto`;
- `google/longrunning/operations.proto`;
- `google/protobuf/any.proto`;
- `google/protobuf/duration.proto`;
- `google/protobuf/timestamp.proto`;
- `google/protobuf/wrappers.proto`;
- `google/rpc/status.proto`.

The REAPI snapshot is therefore a source-file reference, not a compilable proto dependency closure. Any future code-generation or compatibility test must pin the complete import closure and its licenses separately.

## 5. Link-only external references

The reference register also contains live links for standards and tools such as SMT-LIB, cvc5, Lean, LLVM, Rust, C++, SQLite, Git, and Nix. These are not all frozen source snapshots. The register correctly distinguishes link-only references from versioned local snapshots.

Before a research result relies on one of these links as normative evidence, it should record the exact edition, release, commit, or archived source file used. A live documentation URL alone is not a reproducible source identity.

## 6. Documentation correction

The provenance summary in `research/references/README.md` lists MCP, OCI, and Alive2 in its upstream tree-verification table while stating that four upstream revisions were resolved. The manifest includes REAPI as the fourth source, and this audit independently verifies it. Add the missing REAPI row and explicitly state that its proto import closure is not included.

The existing README notes the OCI/Alive2 partial-link state. This audit clarifies that those are completeness limitations, while all 13 stored files remain exact upstream blobs.

## 7. Disposition

**Provenance integrity: verified. Snapshot completeness: intentionally partial for OCI, Alive2, and REAPI.**

No snapshot or license file needs replacement based on this audit. The actionable work is documentation clarification and, only if future experiments require self-contained compilation or browsing, adding the missing OCI/Alive2/REAPI dependency files with their own pinned revisions, blob IDs, and licenses.

No external snapshot content was changed by this audit.
