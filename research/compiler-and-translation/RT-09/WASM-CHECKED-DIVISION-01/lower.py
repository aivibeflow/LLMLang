"""Lower the fixture's checked signed quotient to a Wasm multi-value function."""

import json
import sys
from pathlib import Path


GUARD = """
    local.get $y
    i32.eqz
    if
      i32.const 1
      local.set $status
    else
      local.get $x
      i32.const -2147483648
      i32.eq
      local.get $y
      i32.const -1
      i32.eq
      i32.and
      if
        i32.const 2
        local.set $status
      else
        local.get $x
        local.get $y
        i32.div_s
        local.set $quotient
      end
    end
""".strip("\n")

UNCHECKED = """
    local.get $x
    local.get $y
    i32.div_s
    local.set $quotient
""".strip("\n")


def lower(source, route):
    if (
        source["operation"] != "checked_sdiv_i32"
        or source["signature"] != ["i32", "i32"]
        or source["result"] != ["division_status", "i32"]
        or source["errors"] != ["zero_divisor", "signed_overflow"]
        or source["effectful"] != ["attempt", "settle"]
        or source["pure"] != []
    ):
        raise ValueError("unsupported source contract")
    if route not in ("pure", "guarded", "raw", "reversed"):
        raise ValueError("unsupported lowering route")
    start = ["(module"]
    if route != "pure":
        start.append('  (import "host" "audit" (func $audit (param i32 i32 i32)))')
    start.extend([
        '  (func (export "divide") (param $x i32) (param $y i32) (result i32 i32)',
        "    (local $status i32) (local $quotient i32)",
    ])
    attempt = ["    i32.const 11", "    local.get $x", "    local.get $y", "    call $audit"]
    settle = ["    i32.const 29", "    local.get $status", "    local.get $quotient", "    call $audit"]
    if route in ("guarded", "raw"):
        start.extend(attempt)
    start.append(UNCHECKED if route == "raw" else GUARD)
    if route != "pure":
        start.extend(settle)
    if route == "reversed":
        start.extend(attempt)
    start.extend(["    local.get $status", "    local.get $quotient", "  )", ")", ""])
    return "\n".join(start)


if __name__ == "__main__":
    source = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    sys.stdout.write(lower(source, sys.argv[2]))
