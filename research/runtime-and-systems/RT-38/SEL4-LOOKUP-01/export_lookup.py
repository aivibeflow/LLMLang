#!/usr/bin/env python3
"""Bind the admitted lookup-wrapper fixture to the Isabelle shallow embedding."""

import argparse
import json
from pathlib import Path


def export(source):
    expected_header = {
        "profile": "rt38-capability-lookup-wrapper-v1",
        "parameters": [["thread", "ThreadRef"], ["cptr", "CapabilityPointer"]],
    }
    if (set(source) != {*expected_header, "body"}
            or any(source[name] != value for name, value in expected_header.items())):
        raise ValueError("Unsupported lookup fixture header")
    expected_body = [
        {"bind": "slot", "call": "lookup_slot", "args": ["thread", "cptr"], "on_error": "propagate"},
        {"bind": "capability", "call": "read_slot_capability", "args": ["slot"]},
        {"return": ["capability", "slot"]},
    ]
    if source["body"] != expected_body:
        raise ValueError("Unsupported lookup fixture body")
    return r'''
definition lookup_wrapper ::
  "('state, 'error + 'slot) nondet_monad \<Rightarrow>
   ('slot \<Rightarrow> ('state, 'capability) nondet_monad) \<Rightarrow>
   ('state, 'error + ('capability * 'slot)) nondet_monad"
where
  "lookup_wrapper resolve read_cap =
    bindE resolve (\<lambda>slot. bindE (liftE (read_cap slot))
      (\<lambda>capability. returnOk (capability, slot)))"

definition llmlang_lookup where
  "llmlang_lookup thread cptr =
    lookup_wrapper (lookupSlotForThread thread cptr) getSlotCap"
'''.strip()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("template", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    template = args.template.read_text(encoding="utf-8")
    if template.count("@LOOKUP_DEFINITION@") != 1:
        raise ValueError("Missing unique fixture insertion point")
    args.output.write_text(template.replace("@LOOKUP_DEFINITION@", export(json.loads(args.input.read_text()))),
                           encoding="utf-8")
