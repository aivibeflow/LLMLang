#!/usr/bin/env python3
"""Render the measured ranking summary as a Markdown table."""

import json
from pathlib import Path

labels = {
    "structured": "Structured",
    "lexical": "Lexical",
    "single_vector": "Single vector",
    "multi_aspect": "Multi-aspect",
    "hybrid": "Hybrid",
}

evidence = json.loads(Path(__file__).with_name("evidence.json").read_text())
print("| Ranking channel | Query hits | Compatible recall | Precision@3 | MRR@3 | nDCG@3 | Unsafe first | False unique | Late-filter losses |")
print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
for name, stats in evidence["metrics"].items():
    total = stats["queries"]
    recall = f'{stats["recall_numerator"]}/{stats["recall_denominator"]}'
    quality = " | ".join(f'{stats[key]:.4f}' for key in ("precision_at_3", "mrr_at_3", "ndcg_at_3"))
    errors = " | ".join(f'{stats[key]}/{total}' for key in ("unsafe_top1", "false_unique", "postfilter_loss"))
    print(f'| {labels[name]} | {stats["hit"]}/{total} | {recall} | {quality} | {errors} |')
