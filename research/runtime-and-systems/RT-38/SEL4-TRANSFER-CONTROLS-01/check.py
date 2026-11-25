"""Audit pinned seL4/Isabelle receipts and regenerated lookup source bytes."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from xml.etree import ElementTree


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SESSIONS = ("ASpec", "AInvs", "ExecSpec", "BaseRefine", "Refine")


def read(path):
    return json.loads(path.read_text())


def digest(data):
    return sha256(data).hexdigest()


def cases(xml_path):
    return {case.get("name"): "pass" if len(case) == 0 else case[0].tag
            for case in ElementTree.parse(xml_path).findall(".//testcase")}


def verify_sources(data, related, l4v):
    revision = subprocess.check_output(["git", "-C", l4v, "rev-parse", "HEAD"], text=True, timeout=10).strip()
    assert revision == data["configuration"]["l4v"]
    for path, expected in data["upstream"]["input_sha256"].items():
        assert digest((l4v / path).read_bytes()) == expected, path
    for path, expected in data["wrapper"]["input_sha256"].items():
        assert digest((ROOT / path).read_bytes()) == expected, path
    folder = ROOT / "SEL4-LOOKUP-SOURCE-01"
    for path, expected in related["checked_source_input_sha256"].items():
        assert digest((folder / path).read_bytes()) == expected, path
    for name, row in related["sources"].items():
        raw_bytes = (folder / "sources" / f"{name}.ops").read_bytes()
        assert raw_bytes == bytes(row["bytes"]) and digest(raw_bytes) == row["sha256"], name
    with TemporaryDirectory() as work:
        exported = Path(work) / "Lookup.thy"
        fixture = ROOT / "SEL4-LOOKUP-01"
        subprocess.run([sys.executable, "-B", str(fixture / "export_lookup.py"),
                        str(fixture / "lookup.json"), str(fixture / "Lookup.thy.in"), str(exported)],
                       timeout=10, check=True)
        assert digest(exported.read_bytes()) == data["wrapper"]["generated_lookup_sha256"]
        output = Path(work) / "SourceLookup.thy"
        subprocess.run([sys.executable, "-B", str(folder / "export_bytes.py"), "--output", str(output)],
                       timeout=10, check=True)
        assert digest(output.read_bytes()) == related["generated_source_theory_sha256"]


def check(l4v):
    original = ROOT / "SEL4-LOOKUP-01"
    refined = ROOT / "SEL4-REFINED-LOOKUP-01"
    refined_ledger = read(refined / "evidence.json")
    source_ledger = read(ROOT / "SEL4-LOOKUP-SOURCE-01/evidence.json")
    config = refined_ledger["configuration"]
    assert source_ledger["l4v"] == config["l4v"] and source_ledger["sel4"] == config["seL4"]
    assert not source_ledger["proof_options"]["skip_proofs"] and not source_ledger["proof_options"]["quick_and_dirty"]
    xml = refined / "upstream-refine.xml"
    assert digest(xml.read_bytes()) == refined_ledger["upstream"]["junit_sha256"]
    archived_later = cases(xml)
    recorded = {row["name"]: row["outcome"] for row in refined_ledger["upstream"]["targets"]}
    assert archived_later == recorded and len(recorded) == 9
    earlier = cases(original / "upstream-aspec-refine.xml")
    assert earlier["AInvs"] != "pass" and archived_later["AInvs"] == "pass"
    combined = {**earlier, **cases(original / "upstream-execspec.xml"), **archived_later}
    assert all(combined[name] == "pass" for name in SESSIONS)
    assert source_ledger["upstream_refine_heap_sha256"] == refined_ledger["upstream"]["heap_sha256"]["Refine"]
    assert source_ledger["refined_wrapper_sha256"] == refined_ledger["wrapper"]["input_sha256"][
        "SEL4-REFINED-LOOKUP-01/RefinedLookup.thy"]
    verify_sources(refined_ledger, source_ledger, l4v)
    return {"configuration": config, "upstream_sessions": {name: combined[name] for name in SESSIONS},
            "early_AInvs_disposition": earlier["AInvs"], "successful_refine_prerequisite_runs": len(recorded),
            "verified_upstream_input_digests": len(refined_ledger["upstream"]["input_sha256"]),
            "verified_wrapper_input_digests": len(refined_ledger["wrapper"]["input_sha256"]),
            "verified_source_file_digests": len(source_ledger["sources"]),
            "generated_input_sha256": source_ledger["generated_source_theory_sha256"],
            "source_theorems": source_ledger["proofs"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--l4v", type=Path, required=True)
    print(json.dumps(check(parser.parse_args().l4v), indent=2, sort_keys=True))
