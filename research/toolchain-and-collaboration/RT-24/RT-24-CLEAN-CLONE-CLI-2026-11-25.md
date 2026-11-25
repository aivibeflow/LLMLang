# Rebuild the typed CLI from clean Git clones

This RT-24 study extends the closed graph export comparison to an executable workload. It asks whether a physical Git layout can reproduce the same semantic selections, exact compiled artifacts and CLI behavior without the original local semantic store. It compares a single packed recipe blob with a content-addressed file for each selected entry. [Canonical Git layouts](RT-24-CANONICAL-GIT-LAYOUTS-2026-11-24.md) · [Typed CLI workload](../../language-design/RT-01/RT-01-TYPED-CLI-VERTICAL-SLICE-2026-11-25.md)

## What is restored from Git

Both layouts commit a text manifest, the recipe data and the exact Rust runtime bytes. The manifest pins the selected entry digests, semantic snapshot, runtime digest and installed generator, admission and acceptance inputs. It records the compiler toolchain used by the fixture. The runner clones each independent origin through Git's normal transport path with local object sharing disabled. It checks that the clone has a clean checkout, the requested commit and no alternate or promised object store.

The archive importer uses tracked blobs from the exact Git tree. It checks file modes, the listed inventory and runtime digest, then admits the recipe into a fresh store. The recovered entries and snapshot must match the manifest. A second canonical export must reproduce every tracked blob byte exactly. Only then does the fixture emit and build native programs. The separately installed generator and acceptance tool are pinned inputs rather than part of the project's recipe graph.

```mermaid
flowchart LR
  C[Independent clean Git clone] --> I[Read exact tracked blobs]
  I --> T[Check manifest, runtime and toolchain]
  T --> G[Reconstruct selected graph in fresh store]
  G --> X[Check byte-exact round trip]
  X --> N[Compile all entries with pinned Rust]
  N --> A[Compare process outputs and status]
```

The positive controls include the full Hello, Echo and Calculator workload before and after an isolated Echo separator edit. The edited expectation changes how argument positions are joined. The previous paths and snapshots remain available in the Git history, while the importer takes its inventory from the selected tree alone.

## Results

Both layouts restore two positive clones. Each builds three executables at two optimization levels. All 272 subprocess checks pass. The layouts differ physically and reconstruct equal semantic roots and entry addresses for each revision. Generated source and executable hashes agree across the two layouts for each matched revision and compiler profile. Only the Echo entry changes after the edit.

The table counts logical uncompressed tracked blob bytes. New bytes are the unique blobs present in the edited tree and absent from the baseline tree. The comparison excludes Git pack compression, checkout time and build time.

| Layout | Baseline files | Baseline uncompressed bytes | New blobs after edit | New uncompressed bytes | Removed paths |
|---|---:|---:|---:|---:|---:|
| Packed entries | 3 | 4,561 | 2 | 1,397 | 0 |
| Per-entry content-addressed files | 5 | 4,534 | 2 | 1,017 | 1 |

Per-entry storage writes 380 fewer new uncompressed bytes for this edit and replaces its old content-addressed entry path. The packed layout keeps the recipe path and produces a larger replacement blob. Both require a new manifest.

Ten separate cloned negative controls are refused before compilation. Each layout tests a missing entry, a changed recipe under the old selection, stale runtime bytes, a mismatched installed-generator identity and an unlisted file. In particular, replacing the tracked runtime while keeping the old semantic root and entry map leaves the graph claim intact and fails the separate build-input check.

## Limits and replay

The archive contains a closed three-entry POSIX fixture with a compatible installed type checker and Rust compiler. The input digests capture the tested tool identities. Production sysroot and dependency discovery, arbitrary frontend import, object availability after administrative history rewriting, distributed caches, package authentication, repository-scale measurements and independent review remain open. The experiment provides a scoped clean-clone and round-trip discriminator for the executable path.

Use CPython 3.12.14, native Git 2.52.0 and Rust 1.85.1 on x86-64 Linux. The initial LLMLang baseline is `d5300458f677d7a7d90ab1851d2b21f56f4c2332`. The ledger pins source inputs, exact Git and semantic objects, native artifact hashes and every process observation. Replay from the repository root.

```bash
fixture=research/toolchain-and-collaboration/RT-24/CLEAN-CLONE-CLI-01
PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > /tmp/llmlang-rt24-cli-clone.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt24-cli-clone.json
python3 "$fixture/chart.py"
```

See the [clone and rebuild runner](CLEAN-CLONE-CLI-01/run.py), [measured ledger](CLEAN-CLONE-CLI-01/evidence.json), and [table generator](CLEAN-CLONE-CLI-01/chart.py).
