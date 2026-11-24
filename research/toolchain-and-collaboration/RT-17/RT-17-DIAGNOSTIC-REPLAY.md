# RT-17 — Replay of diagnostic locations and repair proposals

- **Status** · Executable structural evaluation for §7.5
- **Date** · 2026-11-21
- **Baseline** · `f09047a65bc77e8756d9d36def836c193a500dfa`

Can an editor or agent consumer decide where a diagnostic belongs, whether an edit batch still applies, and whether a candidate preserves a declared behavior? This experiment implements part of Scenario 95's discriminator corpus. It uses deterministic inputs and a fixture policy evaluator. Human review and agent repair effectiveness require separate participant runs. [Plan §7.5](../../../PLAN.md#75-developer-experience-and-adoption) · [Scenario 95 discriminator corpus](RESEARCH-SCENARIO-95-EXECUTION-2026-11-20.md#6-discriminating-test-corpus)

## Method and results

The fixture compares numeric offsets and result states with an explicit conversion and applicability policy. The inputs and expected outcomes are declared in the tests. Document bytes are valid UTF-8, locations are half-open, and the workspace is a finite map of immutable document contents. The negotiated position encoding defaults to UTF-16. Tests stage repairs in a new map, with no disk or toolchain write. [Fixture and oracles](../PROTOTYPES/DIAGNOSTIC-REPLAY-01/test_diagnostic_replay.py)

| Scenario 95 cases | Alternative falsified in the fixture | Experimental observation |
|---|---|---|
| DIAG-005 | Use the same integer column for each negotiated encoding. | After `α😀`, the start column is 6, 3, or 2 in UTF-8, UTF-16, or UTF-32. The end of the decomposed `e` plus combining accent is 9, 5, or 4. The converter rejects a location inside the UTF-8 sequence or the CRLF pair. |
| DIAG-006/007/011 | Treat any empty diagnostic list as evidence of success. | An empty complete result is clean at its exact snapshot. Changing a dependency with the entry document unchanged invalidates it. Empty partial, cancelled and unknown results never pass. |
| DIAG-008/009 | Apply a batch as soon as each edit is encountered. | Overlapping edits, two insertions at one offset, an interior byte offset and a stale workspace are rejected. The original map keeps identical content. Valid edits spanning two files produce identical results under reversed input order. |
| DIAG-010 | Accept a repair when compilation succeeds. | Both candidates fix the integer field's type. Only the candidate that preserves the guard meets the expected behavior on all 11 inputs from 0 through 10. Removing the guard admits five forbidden inputs. |

The last oracle is independent of the candidate text and evaluates the policy against `value <= 5`. Compilation checks types only. Replay therefore establishes applicability and exposes a bounded behavioral regression as a separate result. The test uses a JSON policy rather than an LLMLang parser or type checker.

## Implications and limits

Preserve snapshot-bound byte ranges internally and convert to negotiated units at presentation. Treat applicability, validation and permission to publish as distinct inputs to a repair workflow. Full-workspace binding is conservative in this fixture. A narrower dependency-bound snapshot could allow unrelated edits while retaining safety if the affected dependency closure is complete. The fixture does not measure that trade-off, reconstruct diagnostics through an LSP server, identify causes, or establish how often humans or agents make these errors. Content-based IDs also do not record intervening edits that restore identical contents. [Scenario 95 evaluation protocol](RESEARCH-SCENARIO-95-EXECUTION-2026-11-20.md#7-human-and-agent-evaluation-protocol)

## Reproduction

From the repository root, run with CPython 3.12.14 using only the standard library. Expect four passing tests.

```sh
python -B -m unittest discover -s research/toolchain-and-collaboration/PROTOTYPES/DIAGNOSTIC-REPLAY-01 -v
```
