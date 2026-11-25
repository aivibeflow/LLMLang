# RT-00 C — Replay of the Dafny modular proof closure comparison

## Question and scope

Can a fresh Linux runner reproduce the observed distinction between a verified caller, closure over an exact provider body, resource exhaustion and certificate admission? This Stage 0.1 replay uses the unchanged RT-07 fixture published in `00d01dd4b972f319eaf8db80a450e74688fade5e` on `research/all`. The fixture compares a Dafny caller and two interchangeable provider bodies, five Lean theorems about the same arithmetic model, and checks of cvc5 CPC certificates by Logos. [Original design, fixtures and evidence](../../formal-verification/RT-07/RT-07-DAFNY-MODULAR-PROOF-CLOSURE-2026-11-25.md)

A version-string or archive inspection establishes input identity only. Re-executing the same harness checks whether the observations recur. Reimplementing the source-to-model translation or auditing the verifier implementation would test different claims. This replay uses the existing experiment and its [table generator](../../formal-verification/RT-07/DAFNY-MODULAR-PROOF-CLOSURE-01/chart.py). The original report's diagram shows the unchanged proof paths.

## Observations

| Check | Fresh observation |
|---|---|
| Five Dafny cases under each of Z3 4.12.1 and 4.14.1 | All ten dispositions, named obligation outcomes and normalized Boogie hashes matched. Caller-only verification passed with both provider bodies, and checking the included wrong body failed. |
| Resource limit and outer deadline | Both solvers reproduced Dafny's resource-exhaustion category, which shares exit code 4 with the provider verification failure. An injected delay reproduced the outer host timeout. |
| Lean kernel | All five theorem names and their reported axiom lists matched. |
| cvc5 and Logos | Both CPC proofs matched the published bytes. Logos rejected the coarse proof with 35 trust commands and accepted the fine-grained proof with zero. The exact query bound successfully, and the weaker query produced a SAT witness and a binding rejection. The one-unit cvc5 resource limit returned `unknown` with reason `resourceout`. |

The complete replay JSON was byte-for-byte equal to the published ledger, including the fresh Logos executable hash. This demonstrates repeatability for the recorded build and inputs.

## Reproduction

The fresh host ran Debian 13.7 on Linux x86-64 with kernel `6.18.57`, glibc 2.41 and CPython 3.12.14. Extract Dafny 4.11.0 directly from the [upstream Linux x64 Ubuntu 22.04 release archive](https://github.com/dafny-lang/dafny/releases/download/v4.11.0/dafny-4.11.0-x64-ubuntu-22.04.zip); the harness checks the archive hash and records both bundled solver hashes. Build `logos` from the clean upstream checkout at `cf18742973861b3718d04c5f25775448098ff474` with Lean/Lake 4.34.0 from the release distribution.

```bash
(cd "$LOGOS_CHECKOUT" && PATH="$LEAN_434/bin:$PATH" "$LEAN_434/bin/lake" -Kjobs=2 build logos)
fixture=research/formal-verification/RT-07/DAFNY-MODULAR-PROOF-CLOSURE-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" \
  --dafny "$DAFNY_ROOT/dafny/dafny" --archive "$DAFNY_RELEASE_ZIP" \
  --lean "$LEAN_436/bin/lean" --logos "$LOGOS_CHECKOUT" \
  --logos-lean "$LEAN_434/bin/lean" --cvc5 "$CVC5" > /tmp/llmlang-dafny-replay.json
cmp "$fixture/evidence.json" /tmp/llmlang-dafny-replay.json
```

The exact tool versions, proof hashes, normalized Boogie hashes and case outcomes are in the [fresh runner ledger](RT-00-C-DAFNY-MODULAR-PROOF-REPLAY-2026-11-25.json). The [publication ledger](../../formal-verification/RT-07/DAFNY-MODULAR-PROOF-CLOSURE-01/evidence.json) remains the record for the earlier run.

## Implication for LLMLang

For this fixture, preserving the provider's verification scope and exact identity is necessary to tell a conditional caller receipt from closure over the checked provider. The process exit code alone gives insufficient evidence to distinguish a rejected proof obligation from resource exhaustion. The Lean arithmetic model and the separately stated CPC query each have their own source-correspondence obligations. This replay supplies an additional execution record for Stage 0.1. Original-run provenance, source-to-Boogie/Lean/CPC correspondence, general solver coverage, corpus-wide reproduction and independent review remain open. [Corpus reconciliation](https://github.com/aivibeflow/LLMLang/issues/284) · [Solver integration](https://github.com/aivibeflow/LLMLang/issues/295)
