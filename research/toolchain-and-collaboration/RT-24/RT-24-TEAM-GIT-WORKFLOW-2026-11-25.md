# RT-24 — Repository setup and team workflow for semantic merges

This guide describes a candidate integration on the tested Linux Git 2.56.1 profile. Ordinary Git transports commits and trees. The semantic coordinator validates the complete selected graph and produces evidence for publication. The currently tested adapters are bounded research prototypes. [ADR-014](../../../draft/adr/014-git-semantic-merge.md) · [Git integration issue](https://github.com/aivibeflow/LLMLang/issues/322)

## Repository setup

For a team evaluating a conservative fallback, track a `.gitattributes` entry for its actual container paths. This example uses a fixture-only suffix.

```gitattributes
*.spg-fixture -merge
```

The built-in binary policy can keep both file versions unresolved when users edit the same file. Separately edited files can still combine into an invalid graph. A tracked attribute that only names a custom driver may lead Git to fall back to text when local setup is absent. [Six native fallback cases](RT-24-MERGE-FALLBACK-ADMISSION-2026-11-25.md)

For each path classified as semantic, inspect the effective attribute locally. If the team intentionally selected a named driver, confirm which configuration supplies its command and verify the command's installed version through the team's setup. The examples use the driver name `llmlang` and a fixture path.

```sh
git check-attr merge -- example.spg-fixture
git config --show-origin --get merge.llmlang.driver
```

With the binary fallback, the first command reports `unset` and no named driver is required. With named attributes, the first command reports the configured driver name and a missing configuration entry makes that checkout unready for that driver. The second command checks configuration presence. Executable availability and the exact version need separate verification. [Git driver context](RT-24-NATIVE-GIT-MERGE-DRIVER-2026-11-24.md)

## Prepare and review a candidate

Use a clean disposable worktree or integration checkout. Start at the exact current commit and identify the incoming commit after fetching. In the commands below, set `incoming_ref` to the selected incoming ref.

```sh
git status --porcelain
current=$(git rev-parse --verify 'HEAD^{commit}')
incoming=$(git rev-parse --verify "${incoming_ref}^{commit}")
git merge-base --all "$current" "$incoming"
git merge --no-commit --no-ff "$incoming"
git ls-files --unmerged
```

Record the current and incoming commit IDs and every merge-base result. Multiple bases require the selected base-reconciliation policy. If it cannot determine one valid semantic base, keep the candidate pending. When paths are unmerged, preserve the index stages Git actually recorded and bring the complete selected base and parent inventories to the semantic resolution review. A path missing from one stage can represent a deletion. The reviewer needs the exact alternatives, the proposed decision and affected graph scope. The research mergetool adapter tests a repository-bound candidate and rejects stale index inputs. [Multiple merge bases](RT-24-MULTIPLE-MERGE-BASES-2026-11-25.md) · [Native mergetool experiment](RT-24-NATIVE-GIT-MERGETOOL-2026-11-24.md)

Once a merge is pending and no unmerged entries remain, obtain the exact staged candidate tree. Use this step only after verifying that `MERGE_HEAD` identifies the intended incoming commit. An already up-to-date result has no pending merge.

```sh
git rev-parse --verify MERGE_HEAD
git write-tree
```

The coordinator imports the full candidate inventory at that tree, checks graph closure and the required type, contract and dependency evidence, and records a disposition for required tests and proofs. Every applicable check must have satisfied evidence for that exact candidate. A clean Git result or a successful per-file adapter leaves publication pending until the coordinator has an admissible whole-graph result. When evidence is missing or the coordinator is unavailable, retain the candidate in the integration checkout for review or retry. [Closed candidate source inventory](RT-24-MERGED-TREE-SOURCE-COMPLETENESS.md) · [Exact validation audit](RT-24-MERGE-VALIDATION-AUDIT-REPLAY-2026-11-25.md)

## Publish and recover

The integrator reviews the exact staged tree and ordered parents. Publication checks the expected branch tip, the validated candidate and the authorization for that operation. If the tip, index or chosen tree changes during review, collect evidence again for the resulting candidate. Keep the validation receipt, failed checks or unresolved selections linked to their input identities. After publication, verify the commit tree and parents and compare the reconstructed semantic root to the reviewed one. Use a no-local clean clone when testing repository-only reconstruction. [Exact-tree publication](RT-24-TREE-BOUND-CIP-PUBLICATION.md) · [Offline reconstruction](../../packages-and-ecosystem/RT-12/RT-12-OFFLINE-SEMANTIC-CLONE-2026-11-25.md)

If the team abandons a pending merge, save any needed diagnostics and reviewed alternative identities before using `git merge --abort` in that integration checkout. For a failed publication, reconcile the actual ref first and use the coordinator's recovery rule for that observed state. A local hook can prompt validation. The authoritative publication policy must cover the real acceptance endpoint. Rebase and cherry-pick can create different candidate prefixes, so they require their separately validated procedures. [Native hooks](RT-24-NATIVE-GIT-HOOKS-2026-11-24.md) · [Native receive gate](RT-24-NATIVE-RECEIVE-GATE-2026-11-24.md) · [Multi-commit replay](RT-24-MULTI-COMMIT-REPLAY-PREFIXES-2026-11-24.md)

## Verification scope

The command checklist was checked with Git 2.56.1 in a temporary repository. Disjoint semantic-file edits left a pending stage-0 tree. Overlapping edits to one file retained the three original index stages under `-merge`. Both attempts kept the original HEAD, and abort restored a clean index and worktree. Deployment of a production coordinator and native validation on other filesystem profiles are open. [Profile-bound Git paths](RT-24-PROFILE-BOUND-GIT-PATHS-2026-11-25.md)
