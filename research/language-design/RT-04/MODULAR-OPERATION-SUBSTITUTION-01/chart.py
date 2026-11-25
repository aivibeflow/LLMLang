#!/usr/bin/env python3
"""Render direct and modular operation admission outcomes."""

import json
from pathlib import Path

values = json.loads(Path(__file__).with_name("evidence.json").read_text())["counts"]
print("| Check | Cases |")
print("| --- | ---: |")
for field, label in (
    ("cases", "Scoped body and contract pairs"),
    ("directly_conforming", "Native or WebAssembly behavior conforms directly"),
    ("modular_admissions", "Both modular obligations and binding close"),
    ("direct_but_missing_modular_requirement", "Direct conformance with a missing modular obligation"),
    ("false_admissions_with_refinement_only", "Refinement alone admits a nonconforming body"),
    ("false_admissions_with_body_only", "Body conformance alone admits an inadequate provider contract"),
):
    print(f"| {label} | {values[field]} |")
