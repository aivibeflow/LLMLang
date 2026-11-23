#!/usr/bin/env python3
"""Check pinned corpus claim register bookkeeping; NOT scientific claim truth.

Reads report and referenced-source Git bytes from the exact baseline commit.
Checks full Git blobs, cited report line bounds, allowed evidence classes, unique
claim IDs and explicit scope/negative/decision boundaries. Does not execute
experiments, verify formal theorems or accept research/specification decisions.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

CLASSES = {
    "Observation", "Assumption", "Hypothesis / conjecture",
    "Prior-art claim", "Model result", "Experimental result",
    "Proof", "Accepted decision",
}


def _safe_path(path: str) -> bool:
    p = Path(path)
    return bool(path) and not p.is_absolute() and ".." not in p.parts and p.parts[0] != ".git"


def _read_git(root: Path, baseline: str, path: str) -> bytes | None:
    if not _safe_path(path):
        return None
    p = subprocess.run(
        ["git", "-C", str(root), "show", f"{baseline}:{path}"],
        capture_output=True,
    )
    return p.stdout if p.returncode == 0 else None


def _blob(root: Path, data: bytes) -> str:
    return subprocess.run(
        ["git", "-C", str(root), "hash-object", "--stdin"],
        input=data, capture_output=True, check=True,
    ).stdout.decode("ascii").strip()


def validate(root: Path, manifest: dict) -> dict:
    root = root.resolve()
    base = manifest["baseline_commit"]
    errors: list[str] = []
    checked: list[dict] = []
    ids: set[str] = set()
    report_paths: set[str] = set()
    for item in manifest["reports"]:
        path = item["report_path"]
        source = item["reference_path"]
        if path in report_paths:
            errors.append(f"duplicate report path: {path}")
        report_paths.add(path)
        buf = _read_git(root, base, path)
        ref = _read_git(root, base, source)
        report_ok = buf is not None and _blob(root, buf) == item["report_blob"]
        ref_ok = ref is not None and _blob(root, ref) == item["reference_blob"]
        if not report_ok:
            errors.append(f"missing or wrong baseline report blob: {path}")
        if not ref_ok:
            errors.append(f"missing or wrong baseline reference blob: {source}")
        lines = buf.decode("utf-8", errors="replace").splitlines() if buf else []
        if not item.get("evidence_shape"):
            errors.append(f"missing evidence shape: {path}")
        for claim in item["claims"]:
            id_ = claim["id"]
            if id_ in ids:
                errors.append(f"duplicate claim ID: {id_}")
            ids.add(id_)
            evidence_type = claim["primary_evidence_class"]
            if evidence_type not in CLASSES:
                errors.append(f"unknown evidence class: {id_}")
            for prefix in ("report", "boundary"):
                start = claim.get(f"{prefix}_line_start")
                end = claim.get(f"{prefix}_line_end")
                if not (isinstance(start, int) and isinstance(end, int)
                        and 1 <= start <= end <= len(lines)):
                    errors.append(f"invalid {prefix} line range: {id_}")
            for key in ("statement", "scope", "unproven_or_negative",
                        "evidence_level", "draft_impact", "review_status"):
                if not isinstance(claim.get(key), str) or not claim[key].strip():
                    errors.append(f"missing {key}: {id_}")
            checked.append({
                "claim_id": id_, "report": path, "source": source,
                "baseline_report_blob_match": report_ok,
                "baseline_reference_blob_match": ref_ok,
                "primary_evidence_class": evidence_type,
                "technical_truth_reviewed_by_script": False,
            })
    if len(manifest["reports"]) != 12:
        errors.append("expected 12 fixed purposive cohort reports")
    if len(checked) != 24:
        errors.append("expected 24 fixed sample claims")
    return {
        "scope": "baseline Git blob/line accounting, not scientific correctness",
        "baseline_commit": base,
        "reports": len(manifest["reports"]),
        "claims": len(checked),
        "errors": errors,
        "checked": checked,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--manifest", type=Path, default=Path("research/quality-audit/2026-11-23-claim-cohort2.json"))
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = json.loads((root / args.manifest).read_text(encoding="utf-8"))
    result = validate(root, manifest)
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    print(rendered)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered, encoding="utf-8")
    return int(bool(result["errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
