# RT-00 C — Replay two Dafny contract boundary comparisons

## Question and scope

Do the published typed-copy and foreign-interface comparisons reproduce their concrete results on a fresh Linux runner? The copy study uses final arrays and ordered accesses as two observation policies. The foreign-interface study compares a verified caller against the results of separately compiled C providers and their ABI adapters. These checks exercise two ways that contract evidence can have narrower scope than the guarantee a client requires. The original reports show the data and evidence flows for both fixtures. [RT-05 typed-copy study](../../semantic-representation/RT-05/RT-05-DAFNY-SPG-COPY-FRAME-2026-11-25.md) · [RT-07 foreign-interface study](../../formal-verification/RT-07/RT-07-DAFNY-KERNEL-FOREIGN-BOUNDARY-2026-11-25.md)

I reran the existing harnesses at their exact published fixture bytes, from `591c07d3b71f813b97b1cfa5be7f2b8f98825f68` and `329f4c2082fe8dfd77f495128f3fa427111eeacd` in the history of `research/all`. Each complete fresh JSON file matched its corresponding published ledger byte for byte. The [replay record](RT-00-C-DAFNY-CONTRACT-BOUNDARIES-REPLAY-2026-11-25.json) stores the fresh digests, host profile and case summaries. The published [copy observations](../../semantic-representation/RT-05/DAFNY-SPG-COPY-FRAME-01/evidence.json) and [foreign-interface observations](../../formal-verification/RT-07/DAFNY-KERNEL-FOREIGN-BOUNDARY-01/evidence.json) also represent the fresh observation bytes.

## Observations

| Fixture | Fresh outcome | Relevant boundary |
|---|---|---|
| Typed overlapping copy, 5,663 cases per generated profile | Snapshot and directional implementations match every expected final array and stay within the declared access spans. The directional implementation differs from the snapshot trace in 1,505 cases. Removing the forward-copy precondition produces 254 final-state mismatches. The weak destination-only frame admits the extra-write implementation, which differs from the full expected final array in 4,045 cases. | Final-state equivalence and access-trace equivalence are distinct. An applicable verifier receipt includes the exact contract and precondition. |
| Foreign C lookup, 1,836 typed input triples per route and compiler setting | The checked C/unsigned ABI route has zero mismatches. The wrapping, overflow-first and signed-ABI controls produce 376, 738 and 286 mismatches respectively under both GCC O0 and O2. The local dropped-overflow-guard control fails verification with both bundled Z3 versions. | The foreign contract, implementation, ABI adapter and selected error precedence need matching evidence. |

For LLMLang these results replay the cases that distinguish outcome, trace and ABI observations. The copy proof applies to the exact emitted source under the sequential-call assumptions. The foreign execution applies to the finite inputs and compiler/ABI settings exercised here. Source-to-emitter correspondence, universal C behavior, machine-code refinement, broader platform coverage and independent review remain open. [Corpus reconciliation](https://github.com/aivibeflow/LLMLang/issues/284) · [Compatible implementations](https://github.com/aivibeflow/LLMLang/issues/290) · [Proof boundary](https://github.com/aivibeflow/LLMLang/issues/294)

## Reproduction

The runner used Debian 13.7, Linux x86-64 kernel 6.18.57, CPython 3.12.14 and GCC Debian 14.2.0-19. Use the [Dafny 4.11.0 release](https://github.com/dafny-lang/dafny/releases/tag/v4.11.0) x64 Ubuntu 22.04 archive, with the bundled Z3 4.12.1 and 4.14.1 executables. The published harnesses contain the case seeds, release hash and solver limits. Their table generators render the identical results archived above.

```bash
copy=research/semantic-representation/RT-05/DAFNY-SPG-COPY-FRAME-01
ffi=research/formal-verification/RT-07/DAFNY-KERNEL-FOREIGN-BOUNDARY-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$copy/run.py" \
  --dafny "$DAFNY_ROOT/dafny/dafny" --archive "$DAFNY_RELEASE_ZIP" \
  > /tmp/llmlang-dafny-copy-replay.json
cmp "$copy/evidence.json" /tmp/llmlang-dafny-copy-replay.json
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$ffi/run.py" \
  --dafny "$DAFNY_ROOT/dafny/dafny" --release "$DAFNY_RELEASE_ZIP" --gcc /usr/bin/gcc \
  > /tmp/llmlang-dafny-ffi-replay.json
cmp "$ffi/evidence.json" /tmp/llmlang-dafny-ffi-replay.json
```
