# RT-00 C — Scenario 133 current-main generated Rust replay

**Date:** 2026-11-25
**Current main baseline:** `c9cb445c6e68ccae45a362e0bcc95fc4a235198d`
**Evidence type:** source-pinned, bounded native differential replay plus generator unit tests
**Status:** current-main replay passed; original host identity and full clean-historical replay remain distinct/unresolved.

## Question and scope

Does the current committed Scenario 133 generator and runtime still match the Scenario 132 Python reference across its documented transfer, cleanup and alias fixtures, with the required Rust compiler? This is a re-execution of the checked fixture, not a test of arbitrary LLMLang lowering or foreign resources.

The current-main source tree was checked by a fresh GitHub Actions native-reproduction run at checkout `d75fd5474950944a2a101bc419316603abb1fb78`, whose parent was `main` `c9cb445c6e68ccae45a362e0bcc95fc4a235198d`. The runner used CPython 3.12.14; Rust 1.85.1, commit `4eb161250e340c8f48f66e2b929ef4a5bed7c181`, target x86_64-unknown-linux-gnu, LLVM 19.1.7; Linux `7.0.0-1020-azure-x86_64` with glibc 2.43; Python's SQLite 3.53.1 and C SQLite 3.46.1 (source ID ending `alt1`). The full execution is [CI run #45562902629](https://github.com/aivibeflow/LLMLang/actions/runs/45562902629), job `native-reproduction`. The run used the same pinned Rust/LLVM/Python versions as the historical report but a newer hosted OS/kernel and distro tool set, so it is a fresh reproduction, not proof of the original physical host/worktree.

## Method and result

The workflow command is:

```sh
python -B research/PROTOTYPES/RT-04-01/run_native_probes.py \
  --suite all --output-dir artifacts/rt04-native-reproduction
```

The `generated-rust-owned-results` command in that suite compiled all six source/timing fixtures at `opt-level=0` and `opt-level=3`; each has 10,496 inputs. All **125,952** native output rows matched the Python reference. The per-case admitted-start counts matched the archived Scenario 133 table: forwarding 1,856/2,576, recovery 2,816/2,996, and retargeted recovery 2,368/2,590 before/after cleanup. The overall native suite also passed 10 commands with zero failures, zero skips, and no preflight errors. The three focused generator tests passed locally on CPython 3.12.14.

The current source SHA-256 values were:

| Source | SHA-256 |
| --- | --- |
| `rt04_rust_owned_probe.py` | `974e26bbb902cea1116def8c0cbae9c7ffe4eabe00bca751aa9b467950f05c4f` |
| `rt04_owned_probe.rs` | `69610f556ae76755338b3643388ee30e91d47a8830844fa4a7b86acb2a2d50d7` |
| `test_rt04_rust_owned_probe.py` | `f8322a7cdca9cc220722b7ed3362032a2af3d94dc1a50a9241ea4af75b5a29c3` |
| `rt04_return_disposition.py` | `23f8eadbc83cdcd140f994b78fe33a4afeebdc42a5c6c0d9621b9172423cbb5e` |
| `rt04_shared_owned_handlers.py` | `3fad6dad5ddfff1b979c435d8d407e121756104e2fcdf42e1f471896bfb5ff7b` |
| `rt04_shared_owned_workload.py` | `391a80c05dc4ec40e5a813821d419e1e5f15b83e0586698cfb0154eab9cc7ae4` |

## Comparison, limits, and decision boundary

The result agrees with the original report's bounded observation counts on current main and the pinned Rust compiler. The current-main source hashes are newly recorded, and the tests provide a separate generator-validation check. This strengthens reproducibility for the exact fixture and toolchain version.

The replay matches the historical Rust, LLVM and Python versions, but not the full host: current CI ran on Ubuntu 26.04 with kernel 7.0/glibc 2.43, and it does not establish the historical GCC/binutils package identity or original uncommitted state. It does not show that the historical run used these exact current source blobs. No draft or backend-selection decision follows.

Open dependencies are general source-to-Rust correspondence; real foreign-resource/runtime behavior; other targets and compiler versions; and a fully pinned, single-environment reconstruction of the original historical setup if exact host parity is needed. These limits remain external inputs in `PLAN.md`.

## Reproduction

The exact clean-checkout reproduction is the successful [native CI workflow run](https://github.com/aivibeflow/LLMLang/actions/runs/45562902629), which checks out current `main`, sets Rust 1.85.1, builds Python 3.12.14 against SQLite 3.53.1, and runs the native suite. The focused generator tests can be run separately:

```sh
(cd research/PROTOTYPES/RT-04-01 && \
  python3 -B -m unittest -v test_rt04_rust_owned_probe.py)
```

Expected: three unit tests pass; the CI native log contains `125952 native observations match the reference`.
