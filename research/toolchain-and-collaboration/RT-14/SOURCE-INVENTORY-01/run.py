"""Verify a role-labeled catalog against exact Git objects and use cases."""
import argparse
from dataclasses import dataclass, replace
from hashlib import sha256
import json
from pathlib import Path
from subprocess import check_output

BASE = "9f205b677bd0cba9b3806ccb54ab992a3face722"
BENCH = "research/formal-verification/PROOF-OBLIGATION-BENCHMARK/lean-transition-state-results/"


@dataclass(frozen=True)
class Source:
    role: str
    path: str
    anchor: str
    issuer: str
    limit: str


SOURCES = (
    Source("specification", "examples/0003-calculator.md",
           "# 0003 — Integer Calculator", "project", "example behavior"),
    Source("design", "research/toolchain-and-collaboration/RT-24/"
           "RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md",
           "# RT-24 — Canonical Semantic Representation, Diff, and Three-Way Merge",
           "project", "proposal"),
    Source("implementation", "draft/examples/0003-calculator/main.llmlang",
           "operation parse_expression(line: String) -> Result<Expression, CalcError>:",
           "project", "illustrative source"),
    Source("contract", "research/semantic-representation/RT-05/"
           "PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md",
           "| ContractHash | Exact contract value |",
           "project", "candidate contract model"),
    Source("requirement", "research/language-design/RT-02/REQUIREMENT-BACKENDS-01/requirements.json",
           '"failure_frame": "BankAccount shall always satisfy !success -> (new_balance = old_balance)"',
           "project", "fixture requirement"),
    Source("dependency", "research/toolchain-and-collaboration/RT-24/TYPED-SEMANTIC-DIFF-01/evidence.json",
           '"difference_id": "4da4012b6d1f7953a26362a17b277fb094df8e310b47bb63c74d10883df57030"',
           "graph-observation", "archived typed-difference input"),
    Source("diagnostic", BENCH + "false-claim-output.txt",
           "error: Tactic `decide` proved that the proposition",
           "tool-observation", "negative control diagnostic"),
    Source("test", "research/PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_call_site_refactor.py",
           "def test_all_added_edges_and_all_removed_paths_need_an_explicit_account", "verification", "test definition"),
    Source("proof-evidence", BENCH + "summary.json", '"status": "kernel-checked"',
           "verification", "archived checker receipt"),
    Source("documentation", "README.md", "## How the language is designed",
           "project", "overview"),
    Source("external-reference", "research/references/README.md",
           "https://smt-lib.org/papers/smt-lib-reference-v2.7-r2026-09-09.pdf",
           "curated-reference", "version-specific citation only"),
)
EXTERNAL_LOCATOR = SOURCES[-1].anchor
ALLOWED_USES = {
    "describe-inventory": set(source.role for source in SOURCES),
    "retrieve-project-proposal": {"specification", "design", "implementation", "contract", "requirement"},
    "review-recorded-run": {"dependency", "diagnostic", "test", "proof-evidence"},
    "discover-reading": {"documentation", "external-reference"},
}
EXPECTED_COUNTS = dict(zip(ALLOWED_USES, (11, 5, 4, 2)))


def git(*args):
    return check_output(["git", *args])


def read_anchor(source):
    header = git("ls-tree", BASE, "--", source.path).decode().strip()
    metadata, path = header.split("\t")
    mode, kind, oid = metadata.split()
    assert (mode, kind, path) == ("100644", "blob", source.path)
    data = git("cat-file", "blob", oid)
    assert data.count(source.anchor.encode()) == 1, source
    line = data[:data.index(source.anchor.encode())].count(b"\n") + 1
    return oid, line, sha256(data).hexdigest()


@dataclass(frozen=True)
class Candidate:
    snapshot: str
    role: str
    issuer: str
    blob: str
    path: str
    line: int
    sha256: str
    external_locator: str | None


def evaluate(candidate, catalog, use, approved_external=True):
    expected = catalog.get(candidate.role)
    if candidate.snapshot != BASE or candidate != expected:
        return "unbound"
    if candidate.role == "external-reference" and not approved_external:
        return "unapproved"
    return "eligible" if candidate.role in ALLOWED_USES[use] else "out-of-scope"


def check():
    assert git("cat-file", "-t", BASE).strip() == b"commit"
    tree = git("rev-parse", f"{BASE}^{{tree}}").decode().strip()
    catalog = {}
    rows = {}
    for source in SOURCES:
        blob, line, fingerprint = read_anchor(source)
        locator = EXTERNAL_LOCATOR if source.role == "external-reference" else None
        catalog[source.role] = Candidate(BASE, source.role, source.issuer, blob, source.path,
                                         line, fingerprint, locator)
        rows[source.role] = {
            "path": source.path, "issuer": source.issuer, "limit": source.limit,
            "line": line, "blob": blob, "sha256": fingerprint, "external_locator": locator,
        }
    outcome = {}
    for use, expected_count in EXPECTED_COUNTS.items():
        accepted = [role for role, candidate in catalog.items() if evaluate(candidate, catalog, use) == "eligible"]
        assert len(accepted) == expected_count
        outcome[use] = accepted

    use = "describe-inventory"
    implementation = catalog["implementation"]
    proof = catalog["proof-evidence"]
    external = catalog["external-reference"]
    controls = [
        ("source-as-proof", replace(implementation, role=proof.role), use, True, "unbound"),
        ("diagnostic-as-proof", replace(catalog["diagnostic"], role=proof.role), use, True, "unbound"),
        ("unknown-issuer", replace(proof, issuer="commentary"), use, True, "unbound"),
        ("wrong-revision", replace(proof, snapshot=tree), use, True, "unbound"),
        ("same-path-other-blob", replace(proof, blob=catalog["design"].blob), use, True, "unbound"),
        ("wrong-fragment", replace(proof, line=proof.line + 1), use, True, "unbound"),
        ("same-citation-unapproved", external, use, False, "unapproved"),
        ("moving-edition", replace(external, external_locator="https://smt-lib.org/"), use, True, "unbound"),
        ("citation-as-recorded-run", external, "review-recorded-run", True, "out-of-scope"),
        ("proposal-as-recorded-run", catalog["design"], "review-recorded-run", True, "out-of-scope"),
    ]
    control_outcomes = {}
    for name, candidate, purpose, approval, expected in controls:
        observed = evaluate(candidate, catalog, purpose, approval)
        assert observed == expected, (name, observed, expected)
        control_outcomes[name] = observed
    return {"git": git("--version").decode().strip(), "snapshot": BASE, "tree": tree,
            "sources": rows, "eligible_by_use": outcome, "controls": control_outcomes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(check(), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
