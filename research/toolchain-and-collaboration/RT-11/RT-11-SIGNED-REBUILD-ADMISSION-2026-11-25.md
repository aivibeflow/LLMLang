# RT-11 signed cache admission and independent native rebuilds

**Date** 2026-11-25 · **Plan** §3.3 · **Issue** [#300](https://github.com/aivibeflow/LLMLang/issues/300)

Three clean GCC builds in different directories yield the same object bytes from a header-free translation unit. A fourth build of an alternative input yields different object bytes. The action key binds the recorded tool bytes and version, target, fixed command and environment, source digest, and declared fixture path context. The experimental cache predicate verifies Ed25519 signatures with OpenSSL, validates the attestation's action, closure, workspace and policy generation, and filters signers by current authority. It then checks candidate agreement, artifact presence, actual payload bytes and a separately rebuilt object before returning a byte-exact hit.

| Control | Checked result |
| --- | --- |
| Two current authorized signers agree | Exact reuse passes after comparing rebuilt bytes. Duplicate attestations have the same result as a single attestation. |
| Authorized signers disagree | All 120 input permutations yield the same conflict. The conflict remains visible if only one of the claimed payloads is available. |
| A known signer lacks authority or loses authorization | The signer contributes no candidate. The explicit revocation control recovers an exact hit on the authorized result after independent verification. |
| Attestation is signed for an older generation, other workspace, other closure or other key | The attestation is refused as inapplicable. |
| Signed message is altered or signature bytes fail validation | The attestation is refused. |
| Authoritative view is incomplete, artifact bytes are missing or incorrect, or no independent rebuild is available | The cache coordinator returns the corresponding distinct non-hit. |
| The only authorized signer supplies a valid signed result which disagrees with the clean rebuild | The independent comparison refuses the claimed result even though its bytes match its signed digest. |

For exact reuse, require the full current candidate view for the requested scope. Merge authenticated statements by their signed content and evaluate current authorization and exact action applicability before finding conflicts. An unavailable artifact cannot resolve authorized disagreement. Keep the action key, provenance and verified result digest separate. Verify actual bytes on every restoration. In the measured high-assurance policy, an independent rebuild must match before first admission. A production policy could reuse a separately authenticated rebuild receipt under the same action, closure, trust and result scope. This fixture recomputes and compares the rebuild for its eligible controls.

This is a defensive local protocol probe with 18 cases, 120 insertion orders and temporary fixture keys. The three build directories share one pinned host installation. A key registry, authenticated completeness of the index view, inter-machine reproducibility, atomic publication, persistent rebuild receipts and remote artifact lifetime remain open. The native build records a deliberately header-free closure. The independent rebuild check demonstrates byte agreement for that scope and does not validate general dependency discovery.

Reproduce from the repository root with GCC, OpenSSL and Python.

```bash
study=research/toolchain-and-collaboration/RT-11/SIGNED-REBUILD-ADMISSION-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Fresh ephemeral signing keys and independently rebuilt fixture objects reproduced the archived decisions byte for byte. The ledger contains no private keys or run-specific signatures.
