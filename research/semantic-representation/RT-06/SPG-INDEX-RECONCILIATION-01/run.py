#!/usr/bin/env python3
"""Replay the dependency-index candidate and inventory its normative prerequisites."""

from hashlib import sha256
from io import BytesIO, StringIO
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
from tarfile import open as open_tar
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ARCHIVE = "ba145588905bda1c80b150a87bccf75d8da1a647"
PROTOTYPE = "research/PROTOTYPES/DEPENDENCY-GRAPH-01"
INDEX = "research/semantic-representation/RT-06/SEMANTIC-DEPENDENCY-INDEX.md"
DOCS = ("TODO.md", "docs/adr/014-git-semantic-merge.md",
        "docs/adr/015-toolchain-server-semantic-api.md", INDEX)
TESTS = (
    "test_semantic_dependency_index", "test_spg_representation", "test_spg_ordered_lowering",
    "test_spg_admission", "test_recursive_identity", "test_impact_planning",
    "test_scoped_binding", "test_call_site_refactor",
)
DECISIONS = ("LL-001", "LL-004", "LL-005", "LL-006", "LL-008")


def checks(project):
    sys.path.insert(0, str(project / PROTOTYPE))
    from src import impact_planning, semantic_dependency_index

    observed = {}
    for test in TESTS:
        suite = unittest.defaultTestLoader.loadTestsFromName(f"tests.{test}")
        output = StringIO()
        result = unittest.TextTestRunner(stream=output).run(suite)
        if not result.wasSuccessful() or result.skipped or not result.testsRun:
            raise AssertionError((test, output.getvalue()))
        observed[test] = result.testsRun
    return {"semantic_declaration": semantic_dependency_index.SCHEMA_VERSION,
            "dependency_index": semantic_dependency_index.INDEX_SCHEMA_VERSION,
            "impact_plan": impact_planning.CIP_SCHEMA_VERSION}, observed


def status(document, pattern):
    matches = re.findall(pattern, document, flags=re.MULTILINE)
    if len(matches) != 1:
        raise AssertionError((pattern, matches))
    return matches[0]


def decisions(project):
    source = (project / "TODO.md").read_text()
    sections = dict(re.findall(r"^### (LL-\d{3}) [^\n]*\n(.*?)(?=^### |^## |\Z)",
                               source, re.MULTILINE | re.DOTALL))
    open_items = {name: status(sections[name], r"^- \*\*Status:\*\* ([^\n]+)$")
                  for name in DECISIONS}
    adr = {Path(path).stem: status((project / path).read_text(), r"^- \*\*Status:\*\* ([^\n]+)$")
           for path in DOCS[1:3]}
    candidate_status = status((project / INDEX).read_text(), r"^\*\*Status:\*\* (.+?)\s*$")
    assert all(marker == "Open" for marker in open_items.values())
    assert all(marker.startswith("Proposed") for marker in adr.values())
    assert candidate_status.startswith("Research proposal")
    return {"decision_register": open_items, "architecture_records": adr,
            "index_candidate_status": candidate_status}


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as work:
        directory = Path(work)
        snapshot = subprocess.check_output(["git", "archive", ARCHIVE, PROTOTYPE, *DOCS])
        with open_tar(fileobj=BytesIO(snapshot), mode="r:") as archive:
            archive.extractall(directory, filter="data")
        schemas, tests = checks(directory)
        policy = decisions(directory)
        references = {path: sha256((directory / path).read_bytes()).hexdigest()
                      for path in DOCS}
    print(json.dumps({
        "schema": "llmlang-spg-index-reconciliation/1", "python": platform.python_version(),
        "archive_revision": ARCHIVE, "document_sha256": references,
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "candidate_schemas": schemas, "suites": tests, "total_tests": sum(tests.values()),
        "recorded_statuses": policy,
    }, indent=2))
