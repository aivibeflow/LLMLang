"""Compare the quality pilot's discovery rule with explicit nested report selection."""

import argparse
from collections import Counter
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys

sys.path.insert(0, str(Path(".github/scripts").resolve()))
from check_research_quality import inspect, is_new_report
from replay_research_quality_sample import run as replay


def git(*args):
    return subprocess.check_output(["git", *args], text=True)


def proposed_candidate(path):
    name = PurePosixPath(path).name
    return name.startswith(("RT-", "RESEARCH-SCENARIO-")) and name.lower().endswith((".md", ".mdx"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base")
    parser.add_argument("head")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    base, head = [git("rev-parse", ref).strip() for ref in (args.base, args.head)]
    checker_path = ".github/scripts/check_research_quality.py"
    assert git("rev-parse", f"{head}:{checker_path}").strip() == git("hash-object", checker_path).strip()
    added = git("diff", "--name-only", "--diff-filter=A", "-z", f"{base}...{head}", "--", "research/")
    paths = sorted(path for path in added.split("\0") if proposed_candidate(path))
    manual = []
    for path in paths:
        text = git("show", f"{head}:{path}")
        manual.append({"path": path, "warnings": inspect(text)})
    counts = Counter(warning for row in manual for warning in row["warnings"])

    sample_path = "research/quality-audit/2026-11-23-sample.json"
    historical = replay(Path("."), json.loads(git("show", f"{head}:{sample_path}")), from_baseline=True)
    historical_summary = {key: value for key, value in historical.items() if key != "reports"}
    assert historical_summary["blob_mismatches"] == historical_summary["warning_snapshot_mismatches"] == 0

    # Negative control. Section titles and labels are populated with explicit placeholders.
    empty_evidence = """# Illustrative empty control
**Status:** placeholder
**Baseline:** placeholder
**Evidence type:** experimental
**Fixture:** placeholder
**Tool versions:** placeholder
**Expected output:** placeholder

## Question and hypotheses
## Prior sources
## Assumptions
## Experiments
```bash
# Placeholder, no reproduction command supplied.
```
## Results
## Limitations
No negative case was measured.
## Decision boundary
## Draft impact
"""
    control_warnings = inspect(empty_evidence)
    result = {
        "schema": "llmlang-rt00-quality-warning-coverage/1",
        "base": base,
        "head": head,
        "checker_blob": git("rev-parse", f"{head}:{checker_path}").strip(),
        "historical_sample": historical_summary,
        "current_diff_root_selection": [path for path in paths if is_new_report(path)],
        "explicit_nested_selection": manual,
        "explicit_nested_warning_counts": dict(sorted(counts.items())),
        "empty_evidence_control_warnings": control_warnings,
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
