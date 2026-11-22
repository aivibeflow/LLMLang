# RT-00 A — Current-main inventory freshness reconciliation

**Date:** 2026-11-22  
**Repository:** `aivibeflow/LLMLang`  
**Exact audited main commit:** `fc717d9c5a69085d7a524fd6dfc27145f0c35a1c`  
**Manifest:** `research/RESEARCH-CORPUS-INVENTORY-2026-11-20.json`  
**Disposition:** inventory manifest is stale; this report records exact drift and does not claim semantic role review or corpus closure.

## 1. Method

Fetched the recursive Git tree for the exact commit above and compared every tracked blob under `research/` with the manifest's `artifacts` records. The manifest itself is intentionally excluded from the inventory population. Path presence and Git blob SHA were compared directly; tree-reported byte sizes were compared with manifest sizes for changed paths. No path-name-derived RT mapping, prototype role, claim relation, or evidence status was inferred.

The comparison is deterministic for the pinned commit. It does not inspect semantic content of absent records and does not validate experiment reproducibility.

## 2. Exact counts

| Measure | Exact main tree | Manifest |
|---|---:|---:|
| Research files, manifest excluded | 578 | 554 |
| Markdown | 297 | 284 |
| MDX | 3 | 3 |
| Python | 226 | 222 |
| Lean | 33 | 28 |
| Prototype-tree files | 289 | 278 |
| Scenario-named documents | 137 | 137 |

The manifest's `revision` field is `85b3da9014efe1b43399a073e31105fc3d715f40`, not the audited main commit. The manifest has **24 missing paths**, **0 extra paths**, and **20 existing paths whose blob SHA differs** from the audited tree. Changed paths are already represented by path in the manifest.

## 3. Paths absent from the manifest

| Path | Current blob SHA | Bytes |
|---|---|---:|
| `research/CHANGESET-VERIFICATION-AND-ACCEPTANCE-GATE.md` | `284d1f1dbf016d3e26637edd3c4b53c1e29743bd` | 9835 |
| `research/PROTOTYPES/ALLOCATOR-COMPAT-01/probe.rs` | `40f3a1cc16b7d81a2796e3bf99ca9f1fe4cbb018` | 4332 |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/CpcNullaryAliases.lean` | `3d6d177b5f5fea1df758e09811fb526252e6ba85` | 2266 |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/CpcNullaryAliasesTests.lean` | `4e1bf277c657b3036e7210ec3ac6e5aab5969948` | 2001 |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/QuerySymbolRenaming.lean` | `442df6188c00fc4b70d7ed6ca976a7c0b85b4d88` | 3805 |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/SourceWireRefutation.lean` | `2f8570700ef03043033bdd68e35582465ab8989c` | 1084 |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/SourceWireRefutationTests.lean` | `89b1a300ed660b64856f5af36cbf7270bc05d6ce` | 3028 |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt23_mapping_tree_publication.py` | `0d1080e901ec3fe8a8739c94cebc1dd7b59d28ce` | 6190 |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt23_ref_generation.py` | `4f4c2e39e3683b1267bbaca750d163228de539ab` | 4564 |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt24_replay_patch_correspondence.py` | `4e28eb1ae317c2a97506428014fb45d588a6d14f` | 4835 |
| `research/PROTOTYPES/LLVM-PRESERVATION-01/llvm_wasm_view_probe.py` | `e616c5fcbb82143f65ec5e87af4a12b689b073c4` | 2995 |
| `research/PROTOTYPES/LLVM-PRESERVATION-01/wasm_view_host.mjs` | `c0d0a480b804446edd19bfc3060abdf7fea73807` | 1355 |
| `research/RT-00-B-05-02-RT26-CLAIM-TRACEABILITY-PILOT-2026-11-21.md` | `da3ed6efb1f7fcadb41197f5b44fc0ab090f874c` | 7161 |
| `research/RT-07-CPC-NULLARY-ALIAS-BINDING.md` | `066a08d1f9402a970799444447a3cf61505ec3f9` | 3329 |
| `research/RT-07-SOURCE-WIRE-LOGOS-ACCEPTANCE.md` | `2152b3f90eb34447d5f8a7fd024514863838ef90` | 3422 |
| `research/RT-07-WIRE-SYMBOL-RENAMING.md` | `67371a882a6c0745f66344e3431c275dbbc1a643` | 3123 |
| `research/RT-09-STRUCTURAL-TYPE-IDENTITY-LAYOUT-AND-C-ABI-PROPOSAL.md` | `2d7dbe168314f33fae2dada745f2213a2a3a4668` | 22237 |
| `research/RT-13-LLVM-WASM-BYTE-VIEW-LOWERING.md` | `487a20167267b4c22784b483be8e419a753a55ce` | 3564 |
| `research/RT-23-COORDINATED-REF-GENERATION.md` | `90d0c6610be35e1560fef6db4ad82870e556e2df` | 3178 |
| `research/RT-23-MAPPING-TREE-PUBLICATION.md` | `e706b91d5b12608055c4b3e704927f7317f2b996` | 3303 |
| `research/RT-24-SEMANTIC-PATCH-RECONCILIATION.md` | `34ee16caa3c3b0b2f52a22d1feac558f1a8d3f8c` | 2797 |
| `research/RT-25-RUST-SYSTEM-ALLOCATOR-COMPATIBILITY.md` | `8d79d176a93e3eb246311be06d76d9e1064e1d3c` | 3270 |
| `research/STRUCTURE-CONTRACTS-AND-ATOMIC-COMMIT-VERIFICATION.md` | `924b502aed4a2ffa975202ecf950e69662dfada1` | 14967 |
| `research/STRUCTURE-INHERITANCE-COMPOSITION-AND-TEMPLATE-SPECIALIZATION.md` | `928d5f6ee816b0e35c111328d40c6019f5594997` | 16626 |

These are inventory omissions only. Their category, semantic owner, traceability, and content-review depth are not established by this comparison. New structure-contract documents and the acceptance-gate document require content review before RT/Stage mappings are asserted.

## 4. Existing records with stale blob identities

| Path | Manifest blob SHA | Current blob SHA | Old bytes | Current bytes |
|---|---|---|---:|---:|
| `research/LLMLang-CONCEPT.md` | `297c0f2fa929a1a0b37ac7b86f289271b7ad096d` | `68466d87e17b668085b53b8385bae2526aab8d73` | 63412 | 66137 |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/SourceQueryEnvelope.lean` | `542267010d9b47f2e75f3b63ba5551c1fb43c623` | `31e4df896207a254ae961abd6d870ea93424a5cd` | 6069 | 6453 |
| `research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding/lakefile.lean` | `8d3b8efae00fda2dab47699891df2d71024d8b23` | `0ae5c89d9dde4582603c75db37c5d32e3d56a89c` | 1011 | 1076 |
| `research/README.md` | `b881cac706dec62a09094387dfa7359326fd2b03` | `0916c6f0ae18c0d4bb378135f650f5ec5b410559` | 30006 | 31274 |
| `research/RESEARCH-SCENARIO-34-SOURCE-TO-QUERY-SEMANTIC-CORRESPONDENCE.md` | `e724812199acd887ae955a9bee8a69b3a63526a8` | `379f9450afed5f5708713f0120e69377a95e4a49` | 35683 | 36077 |
| `research/RT-00-A-INVENTORY-MANIFEST-FRESHNESS-RECONCILIATION-2026-11-21.md` | `4764d57b5ac5ead4818831eae8f4e2fb291c8b55` | `c3bc1006dc2df267103b70693d269a447b8a003a` | 31401 | 31400 |
| `research/RT-00-B-05-COMPLETE-TRACEABILITY-GRAPH-AUDIT-2026-11-21.md` | `0fb22a05eac78419be2d68e3c909f9a02c529dad` | `1374a2b80b1657ac62b3faa2381014df7ea371e5` | 26593 | 39148 |
| `research/RT-00-B-06-UNIFIED-CONTRADICTIONS-AND-UNRESOLVED-REGISTER-2026-11-21.json` | `57d5004429400851fd9cf1c23327a5bd344860ca` | `e66204f33a755af9f760a8b695509e814fa96970` | 37726 | 39491 |
| `research/RT-00-B-06-UNIFIED-CONTRADICTIONS-AND-UNRESOLVED-REGISTER-2026-11-21.md` | `e0b9af362716e6567e462daac175facd83d74293` | `65a2f50c7dcd09e5905e2e7e211729bc0e93e6a1` | 25597 | 34232 |
| `research/RT-00-C-REPRODUCIBILITY-AUDIT-2026-11-20.md` | `b94c89afd431178ff5bfa49a579e55cce4ace161` | `06d7064ba9a3c8d3b8f29f838fe0fe1f99a6affb` | 20127 | 23334 |
| `research/RT-00-E-GLOBAL-LINK-AND-ANCHOR-AUDIT-2026-11-21.md` | `5f8cc17822d0f3433d2e2d440b79b21cce585a6e` | `dad6ef8ca2a20bf3deda410b52cc43a7effc92bd` | 5242 | 6496 |
| `research/RT-04-ORDERED-CALL-EFFECT-SUMMARIES.md` | `c3a40466fd7ab52743e1c211ebd9ddaff9d81dbb` | `beb0148f488d672fbdf37c593505df44f7e4b6cc` | 3450 | 3456 |
| `research/RT-04-TYPE-EFFECT-OWNERSHIP-AND-CAPABILITY-ALTERNATIVES.md` | `ce6c257473b3ad1daa82a21f3df43e995378d054` | `39b4f6864499c100d462faeeec19ac6739b13527` | 35100 | 36129 |
| `research/RT-06-SCOPED-BINDING-READ-DEPENDENCIES.md` | `2a8e56e2e25a1564a88a553b88bdd7c8088a6851` | `09f9ad447aca0844c1e3741d56bf5576f1f513ff` | 3873 | 4511 |
| `research/RT-09-ORDERED-SPG-LOWERING.md` | `738be0dc2e19537be3fcb4c77a651188191eb145` | `df899fb22439f42b989f059a6852ad26644d4cd4` | 4475 | 5114 |
| `research/RT-22-LLMLANG-GIT-REPOSITORY-AND-WORKTREE-MCP.md` | `8bf14febdbdc6ab90a30fe985a856f5b8fdf2da6` | `1f2779e5d7672c2a9d5b377df31c08cca1ccfacd` | 18687 | 27772 |
| `research/RT-24-CALL-TARGET-MERGE.md` | `68b61bd718a9753aaf8693e74a5de875144dce68` | `e37a99c8a609c2640aae8063776a6cdf8135298b` | 3533 | 4190 |
| `research/RT-25-MEMORY-ALLOCATOR-COMPATIBILITY-AND-BENCHMARKING.md` | `2400e3a95028eaa2d210ba411902f89e607a50b5` | `f29041a11f1be8340b43cee4b58dbe96b83de565` | 8139 | 8202 |
| `research/RT-26-CANCELLATION-ACCOUNTING.md` | `701acf13f81d017a18c7650e632ab9da91ceada9` | `937d33e06d1275ecfe9b53a052e33266c6dad319` | 3575 | 4223 |
| `research/RT-26-HIERARCHICAL-RESOURCE-ACCOUNTING-AND-ENFORCEMENT.md` | `eccbea239f2469c391ee7832a27e1b78c2d6a45b` | `47277c95fd8baf3b9c5daf48355fa701fcb37f68` | 14555 | 14798 |

A changed blob does not imply semantic change of a particular kind. It establishes only that the manifest's stored content identity and byte size are stale.

## 5. Prototype and Scenario review boundary

The current tree contains 289 paths under `research/PROTOTYPES/`; the manifest has records for 278 of them, so 11 prototype paths are absent from the manifest. All represented prototype paths have traceability metadata, but that is metadata presence, not proof that each artifact received equivalent content review, execution, or independent reproduction.

The current tree contains 137 Scenario-named documents and the manifest has 137 such records. This count agreement does not validate every scenario-to-RT mapping, claim, test outcome, or evidence edge. The manifest's category count labels 136 artifacts as `scenario-research-result`; this is not directly interchangeable with the filename-pattern count because supplemental execution and other scenario-related documents can have different categories.

No aggregate prototype role-review field exists in the current manifest schema at the audited revision. Therefore historical 242/245/248 role-review totals cannot be reconciled by reading the current manifest alone. A separate content-level family review is still required.

## 6. Required follow-up

1. Refresh the manifest against the exact main tree, preserving existing metadata where still valid and recording explicit unresolved status for new items until content review.
2. Review the 24 newly absent paths individually; do not infer semantic ownership from filenames.
3. Reconcile prototype-family role-review counts from an explicit per-path review ledger, distinguishing path inventory, traceability metadata, content review, test execution, and independent reproduction.
4. Re-run semantic duplicate/supersession/orphan/contradiction checks against the refreshed corpus.
5. Update the RT-00 G report only after the A refresh and the remaining B–F evidence are integrated.

**Conclusion:** Stage 0.1 remains open. This report supersedes older numeric snapshots only for the exact tree commit named above. It does not close RT-00 and does not establish a language or architecture decision.
