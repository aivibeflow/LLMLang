# RT-00 C — Adjudicate negative-result warnings in nested research reports

## Question and source

Do the warning-only structure checks identify a missing negative result in the 18-report post-relocation cohort? I reviewed all seven reports for which the exact checker returned the negative-result warning. The source is the [pinned nested cohort](QUALITY-WARNING-COVERAGE-01/evidence.json) at `bf4308bd7519859f82e1a520aa2cef2c19295c7d` on `research/all`. This follows the distinction in the [earlier boundary study](RT-00-C-NEGATIVE-RESULT-CURRENT-MAIN-RECHECK-2026-11-25.md) between a falsifying observation, an unsupported case and a finding limited by scope.

I searched the pinned source for the disposition of an explicit alternative, counterexample, or applicability limitation, then compared it to the scope of its reported evidence. The table gives all seven outcomes and exact source lines. A diagram would repeat the table without making the dispositions clearer.

## Adjudications

| Report | Exact source lines | Recorded outcome and class |
|---|---:|---|
| [Binary64 relationship review](RT-00-B-15-F64-RELATIONSHIP-REVIEW-2026-11-25.md) | 38–46 | **Scoped falsification.** Replacing input NaNs changes 216 of 1,024 glibc extrema pairs while using the same NaN output projection. The measured difference refutes input canonicalization for these extrema observations. |
| [Explicit relationship screen](RT-00-B-16-EXPLICIT-RELATIONSHIP-SCREEN-2026-11-25.md) | 21–42 | **Observed coverage misses.** The rule retrieves two of four known control pairs. Five of eight selected pairs have cues about other relationships or context. |
| [Dafny contract boundaries replay](RT-00-C-DAFNY-CONTRACT-BOUNDARIES-REPLAY-2026-11-25.md) | 11–14 | **Counterexamples to scope extension.** Removing a precondition, weakening a frame, varying C behavior or changing ABI signedness produces concrete discrepancies in the reported cases. |
| [Draft boundary recheck](RT-00-C-DRAFT-BOUNDARY-CURRENT-MAIN-RECHECK-2026-11-25.md) | 19–26 | **Unsupported validation route.** The pinned validator lacks support for the saturating path. The audit also records the scope of evidence for a foreign contract. Neither finding establishes an implementation decision. |
| [Direct draft citations audit](RT-00-C-DRAFT-CITATION-RESEARCH-ALL-AUDIT-2026-11-25.md) | 17–21 | **Scoped zero observed.** The citation review located no instance that widened the decision and found a two-step citation through the index. The completed check applies to the eight draft files on the pinned tree. |
| [Evidence ledger identities](RT-00-C-EVIDENCE-LEDGER-IDENTITIES-2026-11-25.md) | 40–46 | **Counterexample to filename-only binding.** One evidence key names an imported helper rather than the adjacent runner. Another names a different fixture's evidence. Exact path context resolves both. |
| [Recovery relationship review](RT-00-RT19-RT23-RECOVERY-RELATIONSHIPS-2026-11-25.md) | 38–44 | **Counterexample to extended atomic visibility.** One scheduled Git files-backend read observes the ref advanced before the receipt is visible. The observation bounds the historical result and does not establish behavior on other backends. |

All seven flagged reports record relevant scope information. Five contain falsifying observations, counterexamples or missed controls, one identifies an unsupported validation route, and one reports a scoped search with zero instances. A zero result for a scoped search is an answer to its own question. It provides no evidence about unreviewed snapshots. A validator's unsupported operation likewise supplies a coverage limit; it gives no judgment about the underlying operation.

For LLMLang's research review, use the reported disposition to determine whether an alternative can be ruled out under the applicable contract, remains unresolved under available tools, or was absent from a checked dataset. Warning counts can help locate reports for inspection. The seven selected cases give no error-rate estimate for the remaining eleven or the wider corpus. This review supplies a proposed claim classification and leaves independent adjudication and quality-policy adoption open. [Stage 0.2 tracking](https://github.com/aivibeflow/LLMLang/issues/285)

## Reproduction

The pinned cohort command is documented in the [structural warning coverage report](RT-00-C-QUALITY-WARNING-COVERAGE-2026-11-25.md). The following CPython 3.12.14 command lists the exact warning population. Use the listed paths with `git show bf4308b:<path>` for the line references above.

```bash
python3 - <<'PY'
import json
from pathlib import Path

fixture = Path("research/research-management/RT-00/QUALITY-WARNING-COVERAGE-01/evidence.json")
cohort = json.loads(fixture.read_text())
warning = "negative/rejected/UNKNOWN cases or justified N/A not located"
selected = [row["path"] for row in cohort["explicit_nested_selection"] if warning in row["warnings"]]
assert len(cohort["explicit_nested_selection"]) == 18
assert len(selected) == 7
print("\n".join(selected))
PY
```
