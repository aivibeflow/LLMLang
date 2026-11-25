# RT-34 parallel, expected and output-sensitive resource models

**Date** 2026-11-25 · **Plan** §2.0, CX-12–14 · **Issue** [#412](https://github.com/aivibeflow/LLMLang/issues/412)

The experiment checks three scoped resource profiles. All costs use explicit units and size domains. Six Lean propositions check the balanced-tree counts, critical-path arithmetic, uniform-expectation numerator and output-width inequalities. The Python runner compares independently constructed finite observations in each profile.

## Parallel reduction

A Boolean input has length `n`. There are `p = 2^d` logical lanes. Each lane scans a contiguous block of at most `ceil(n / p)` entries, with empty lanes padded by false. A full binary tree reduces the lane outputs. One counted operation reads and accumulates one input, or combines two child results. The communication metric counts one message per child-to-parent tree edge, including neutral lane messages. It excludes scheduling and latency.

| Metric | Model result |
| --- | ---: |
| Total work | `n + p − 1` |
| Longest dependency path | `ceil(n / p) + d` |
| Messages | `2(p − 1)` |

The runner builds the dependency DAG, evaluates its longest path, and compares Boolean results with serial existence. All 10,235 cells agree over every input of size 0–10 and one to 16 lanes. For `n = 10`, increasing from one to four lanes changes the work from 10 to 13, the span from 10 to five and the messages from zero to six. Actual parallel deployment and machine time remain open.

## Probe expectation

A serial scan terminates at the first true value. With exactly one true value drawn uniformly from all positions, the expected number of probes is `(n + 1) / 2`. Mixing that distribution with a quarter point mass on the last position changes the expectation to `(5n + 3) / 8`. Mixing it with a half point mass on a wholly absent input changes the expectation to `(3n + 1) / 4`. The worst-case count remains `n`.

An exact rational replay checks the three expectations using 8,256 positive and 128 absent inputs across sizes 1–128. The three expected counts differ at 127 sizes. The symbolic sum establishes the uniform numerator. Each mixture uses its declared mass. Randomized algorithms with adaptive adversaries, correlated inputs and statistically estimated distributions remain open.

## Output-sensitive materialization

A selection action receives `n` entries and emits `k ≤ n` fixed-width selected records with width `w > 0`. The byte count is `k × w`. The runner materializes 612 byte outputs and checks every record and length. When `w ≤ W`, Lean proves the upper bound `n × W`. For every fixed positive `n` and candidate byte budget, Lean chooses a valid one-record output whose width exceeds the budget. A single-variable size bound requires an explicit width restriction or a different size measure.

The foci are DAG work and communication, exact finite expectations, and materialized output bytes. Hardware and network measurements, broad bit-complexity models, automated model inference and independent benchmark adjudication remain open.

Reproduce with Lean 4.36.0 and Python from the repository root.

```bash
study=research/formal-verification/RT-34/PARALLEL-EXPECTED-OUTPUT-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two independent replays produced the same ledger. The axiom audit reports only `propext` and `Quot.sound` where present.
