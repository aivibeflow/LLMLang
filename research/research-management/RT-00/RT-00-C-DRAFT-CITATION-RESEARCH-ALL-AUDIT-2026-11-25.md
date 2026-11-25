# RT-00 C — Draft citations to research on `research/all`

## Question and method

Does the current candidate specification cite research material in a way that widens an accepted decision? The [previous recheck](RT-00-C-DRAFT-BOUNDARY-CURRENT-MAIN-RECHECK-2026-11-25.md) inspected recent changes and selected reports. This audit instead inspects all direct draft-to-research citations at the single `research/all` revision `41ce460f60ce9965145ed5767a94b0983e32b5b5`. A history-wide review would address the separate question of how decisions and references changed over time.

I enumerated every tracked draft file, inspected each occurrence of `research/`, resolved every direct link against the pinned Git tree, and checked the single heading fragment. I read the enclosing draft text, the accepted decision's scope and the status and scope of the cited materials. The ledger stores each citation occurrence, its source line, the destination object ID, any fragment and the manually assessed citation role. The table gives the full source-to-role breakdown. A diagram would repeat the citation ledger without adding information. [Citation ledger](RT-00-C-DRAFT-CITATION-RESEARCH-ALL-AUDIT-2026-11-25.json)

## Result

| Source | Tracked files | Direct research citations | Assessment |
|---|---:|---:|---|
| Draft glossary | 1 | 12 | Links support proposed terms for types and ABI, contracts and conformance, public interfaces, and proof assumptions. The glossary labels itself a terminology proposal. |
| Architecture decision | 1 | 4 | The three background citations and the related public-interface proposal do not add requirements to the accepted component immutability and single-toolchain build compatibility decision. |
| Draft index | 1 | 2 | One link navigates to the research directory and the other identifies a candidate public-interface proposal as non-normative. |
| Example index, three candidate programs and directory placeholder | 5 | 0 | The examples identify their sketch and testing status. |
| Total | 8 | 18 | All 12 distinct destinations resolve, including one directory and one heading fragment. |

The architecture decision's label for Scenarios 109–111 points to the broad research index section. That section links to all three named studies, so the citation resolves but requires a second navigation step. The decision itself classifies those three studies as bounded serialization experiments and Scenario 134 as comparative prior art. Its scope excludes cross-toolchain ABI and wire-schema evolution requirements. [Architecture decision](../../../draft/ARCHITECTURE-DECISIONS.md) · [Research index section](../../README.md#core-semantic-and-type-research) · [Scenario 134](../../packages-and-ecosystem/RT-18/RESEARCH-SCENARIO-134-WIRE-SCHEMA-EVOLUTION-INTEROPERABILITY.md)

The audit found no instance of a direct citation widening the accepted decision in this snapshot. For LLMLang, the citation role and the cited claim's scope are relevant during synthesis. A link to a finite pilot or a prior-art comparison provides traceability, while transferring a rule requires an explicit architectural decision and its own evidence. This checks the citation boundary at the pinned tree. Historical completeness, technical validation of the cited claims, independent review and approval of the proposed quality protocol remain open. [Stage 0.2 issue](https://github.com/aivibeflow/LLMLang/issues/285)

## Reproduction

Git 2.56.1 and CPython 3.12.14 were used on Linux. The first two commands reproduce the draft file inventory and the 11 citation-bearing lines. The rest verify each ledger entry against the pinned objects and confirm the sole cited heading.

```bash
rev=41ce460f60ce9965145ed5767a94b0983e32b5b5
git ls-tree -r --name-only "$rev" -- draft
git grep -n -F 'research/' "$rev" -- draft
python3 - <<'PY'
import json
import re
import subprocess
from pathlib import Path

path = Path("research/research-management/RT-00/"
            "RT-00-C-DRAFT-CITATION-RESEARCH-ALL-AUDIT-2026-11-25.json")
ledger = json.loads(path.read_text())
rev = ledger["revision"]

def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()

assert git("ls-tree", "-r", "--name-only", rev, "--", "draft").splitlines() == ledger["draft_files"]
expected_links = set()
for row in ledger["citations"]:
    target = f"{rev}:{row['target']}"
    assert git("cat-file", "-t", target) == row["target_type"]
    assert git("rev-parse", target) == row["target_object"]
    lines = subprocess.check_output(["git", "show", f"{rev}:{row['source']}"], text=True).splitlines()
    url = "../" + row["target"]
    if row["target_type"] == "tree":
        url += "/"
    if row["fragment"]:
        assert row["fragment"] == "core-semantic-and-type-research"
        assert git("show", target).splitlines().count("## Core semantic and type research") == 1
        url += "#" + row["fragment"]
    assert f"]({url})" in lines[row["line"] - 1]
    expected_links.add((row["source"], row["line"], url))

observed_links = set()
for entry in git("grep", "-n", "-F", "research/", rev, "--", "draft").splitlines():
    _, source, line, content = entry.split(":", 3)
    for url in re.findall(r"\]\((\.\./research/[^\s)]*)\)", content):
        observed_links.add((source, int(line), url))
assert observed_links == expected_links
assert len(observed_links) == len(ledger["citations"]) == 18
print("Verified 18 direct draft-to-research citations.")
PY
```
