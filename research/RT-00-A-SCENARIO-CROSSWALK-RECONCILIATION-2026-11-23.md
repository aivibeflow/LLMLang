# RT-00 A — Scenario Crosswalk Reconciliation (2026-11-23)

**Research item:** `PLAN.md` §0.1 — Reconcile the research corpus  
**Baseline:** current `main` `3fb0a1ac8f652cacf21c486b1b0cc26789b2ad2f`  
**Question:** Does the 137-versus-136 count identify a Scenario report omitted from the crosswalk?  
**Disposition:** No omitted report was found. The difference came from mixing a broad path-name count with the strict Scenario-report set.

## Method and exact counts

Enumerated tracked paths using `git ls-tree -r --name-only HEAD research`. Reproduced the two filename predicates involved:

- Broad count: path contains `SCENARIO-` followed by digits, case-insensitively: **137 paths**.
- Report count: path begins `research/RESEARCH-SCENARIO-` followed by digits: **136 report files**.
- The single broad-only path is `research/RT-00-B-05-01-SCENARIO-130-CLAIM-TRACEABILITY-PILOT-2026-11-21.md`. It is a Stage 0 claim-traceability pilot whose filename names the subject Scenario 130; it is not a Scenario report.
- The 136 report files map to candidate RT areas in the crosswalk. They represent **135 scenario identifiers** because Scenario 95 has a main report and a supplemental execution record. Scenario 16 has no report; whether it was reserved or omitted remains unresolved.

The result is reproducible with:

```python
paths = subprocess.check_output(
    ["git", "ls-tree", "-r", "--name-only", "HEAD", "research"], text=True
).splitlines()
broad = [p for p in paths if re.search(r"SCENARIO-\d+", p, re.I)]
reports = [p for p in paths if re.match(r"research/RESEARCH-SCENARIO-\d+", p, re.I)]
assert len(broad) == 137
assert len(reports) == 136
assert set(broad) - set(reports) == {
    "research/RT-00-B-05-01-SCENARIO-130-CLAIM-TRACEABILITY-PILOT-2026-11-21.md"
}
```

## Correction and limits

The prior inventory's `scenario_named_documents` field is a broad filename-pattern count, not a report count. The semantic crosswalk's `total_scenario_files` and `mapped_scenario_files` are strict report counts. Their difference was falsely described as an unresolved missing mapping. This correction names the counting predicates and preserves both metrics instead of conflating them.

This closes only the filename-count discrepancy in the current-main inventory. Scenario 16's intent remains externally unresolved; the crosswalk is first-pass RT mapping, not claim validation, experiment reproduction, or a complete semantic overlap review. Historical snapshots retain their original counts and interpretations as historical records.
