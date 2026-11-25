# RT-33 VAC-02 source-bound CPC and Alethe artifact replay

[Lean, Logos and SMT integration / #295](https://github.com/aivibeflow/LLMLang/issues/295) · [Verification artifact cache work packages](VERIFICATION-BACKEND-INTEGRATION-AND-ARTIFACT-CACHE.md)

An UNSAT result can support a source claim only through the exact query it refutes and a scoped certificate checker. This fixture lowers an immutable source record to two assumptions over a declared integer `x`. The query asks whether `x` can equal the required value while differing from an excluded value. The independent expectation is SAT exactly when the values differ. cvc5 emits raw CPC and Alethe output. The replay stores both certificates and their exact source/query bindings in a SQLite content-addressed store.

```mermaid
flowchart LR
    S[Current immutable source] --> Q[Render exact SMT-LIB]
    Q --> C[Generate cvc5 certificate]
    C --> B[Store source, query and certificate by digest]
    B --> L[Lookup exact format, policy and checker identity]
    Q --> L
    L --> P[Logos CPC or Carcara Alethe]
    P --> O[Create checked source-bound receipt]
    Q --> Z[Z3 verdict and concrete model comparison]
```

Logos checks the CPC derivation after comparing the declared sort and ordered assumptions with the exact parsed query. Carcara checks the Alethe proof with the exact SMT-LIB file and with no external arithmetic solver enabled. The fixture accepts only the positive checker verdict for either format. The cvc5 verdict alone carries no certificate. Z3 runs a separate solver and supplies a concrete model in the SAT case.

## Observations

| Current source | Old exact receipt | Recheck original certificate | Fresh cvc5 certificate | Z3 |
| --- | --- | --- | --- | --- |
| Original contradiction | Hit | Checked in both formats | Checked | UNSAT |
| Revised source metadata, identical query | Miss | Checked and recorded under a new source receipt | Identical proof output | UNSAT |
| Changed values, still contradictory | Miss | Both refused | New certificates checked | UNSAT |
| Changed values, satisfiable query | Miss | Both refused | No proof | SAT, `x = 3` |

Each row was exercised in both formats. A reopened SQLite connection recovered the original two proof records with exact bytes and distinct identities. Two equivalent-wire records and two freshly generated records increased the total to six. A metadata change therefore loses exact receipt reuse even when the same certificate can be checked against the regenerated query. A change to the refuted assertions requires a new certificate. The Z3 model was also evaluated independently against the fixture's required and excluded values.

Eight controls cover changed checker identity, invalid rules, and a bare UNSAT verdict in both formats, plus a corrupted stored payload and an Alethe proof with a hole. Carcara reported `holey` and the gate declined that result. The corrupt CPC payload failed before checker invocation while the separate Alethe entry remained readable.

The replay covers one integer declaration, two ordered assumptions and the observed contradiction proofs. It does not establish general SMT-LIB source correspondence, arbitrary Alethe/CPC support, an accepted checker TCB, or a measured speedup. The checkout and compiled Logos modules, cvc5, Carcara, Z3, and Lean runtime identities are recorded. [Related typed CPC correspondence experiment](../RT-07/RT-07-SOURCE-CPC-PROOF-REBINDING-2026-11-25.md) · [VAC-03 Lean artifact replay](../RT-32/RT-32-LEAN-ARTIFACT-REPLAY-2026-11-25.md)

## Reproduce

Run from the repository root with CPython 3.12.14 and SQLite 3.53.1. Set the tool variables to real binaries for cvc5 1.4.2, Carcara 1.1.0, Z3 4.13.3 and Lean 4.36.0, and set `LOGOS_CHECKOUT` to the clean compiled Logos checkout at `cf18742973861b3718d04c5f25775448098ff474`. The Carcara executable used here was built from [the tagged source](https://github.com/ufmg-smite/carcara/tree/5d817d86bd18ea2a850a580d602f17f36959ee99) with Rust 1.85.1 and `cargo build --locked --release -p carcara-cli`. A rebuild under different toolchain or executable paths can leave distinct binary hashes and receipt identities while reproducing the decisions. [Fixture](SMT-ARTIFACT-REPLAY-01/) · [Raw solver outputs and checkers](SMT-ARTIFACT-REPLAY-01/evidence.json)

```sh
fixture=research/formal-verification/RT-33/SMT-ARTIFACT-REPLAY-01
python -B "$fixture/run.py" --lean "$LEAN_BIN" --cvc5 "$CVC5_BIN" \
  --carcara "$CARCARA_BIN" --z3 "$Z3_BIN" --logos "$LOGOS_CHECKOUT" \
  --output /tmp/rt33-vac02-replay.json
cmp /tmp/rt33-vac02-replay.json "$fixture/evidence.json"
```
