# Independent replay of four directional translation profiles

[GitHub #328](https://github.com/aivibeflow/LLMLang/issues/328) · 2026-11-25

The automated replay distinguishes importing source into the typed model, generating executable code from the model, and composing both operations. The source fragment is closed wrapping 32-bit addition, subtraction or multiplication, with a noninterfering writable output slot and returning callbacks. The compared observables are status, output slot value and ordered callbacks.

| Direction | Profiles | Checked evidence |
| --- | ---: | --- |
| C, C++, Go or Rust → checked model | 4 | Twelve accepted source programs per language preserve the typed operations and operands. |
| Checked model → C, C++, Go or Rust | 4 | 148,080 native observations. |
| Source language → checked model → same language | 4 | 148,080 native observations in the common matrix. |
| Source language → checked model → different language | 12 | 444,240 native observations in the common matrix. |

The combined matrix replays 740,400 native observations. The separate round-trip experiments replay another 666,360 observations across C-family optimization profiles, original and regenerated Go, and Rust optimization and overflow-check profiles. These runs share a bounded corpus, so the totals count executions across routes and configurations. The separate C-family and Rust results also match the common full trace digest.

Native runs and import checks establish different claims. The audit reproduces 37 importer refusals across the four languages and rejects six modified summaries, including a missing route, changed trace digest, missing imported program and an emission result promoted to a verified round trip. Successful compilation is one input to the forward claim. Exact typed import, target execution and full observations are checked where each direction requires them.

The four archived ledgers reproduce on current source. The audit checks all recorded source digests and compares the full replay ledgers after omitting only Clang's machine-dependent installation directory. It retains compiler versions, original archive digests and normalized replay digests. It confirms one restricted input profile. General language semantics, parser completeness and other OS and ABI profiles remain open.

## Replay

Use CPython 3.12.14, Clang 19.1.7, Go 1.27.4 and Rust/Cargo 1.85.1 on Linux x86-64. Load the locked Rust parser dependencies in Cargo before its offline builds. The Go archive used for this replay has SHA-256 `7226736c2339719cda28fbf3a54d71aa63bcefe376e98cef00034268dab24840`.

```sh
directory=research/compiler-and-translation/RT-30
cargo fetch --locked --manifest-path "$directory/RUST-WRAPPING-ROUNDTRIP-01/Cargo.toml"
python "$directory/DIRECTIONAL-REPLAY-01/run.py" --clang /path/to/clang19 \
  --go /path/to/go1.27.4 --output /tmp/rt30-directional.json
cmp "$directory/DIRECTIONAL-REPLAY-01/evidence.json" /tmp/rt30-directional.json
```

Two fresh replays produced identical [audit ledgers](DIRECTIONAL-REPLAY-01/evidence.json).
