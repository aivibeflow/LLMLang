"""Lower the fixture's two ordered effects to an explicit C runtime ABI."""

import json
import sys
from pathlib import Path


def emit(program, reverse):
    if program["name"] != "emit_pair" or program["inputs"] != ["left", "right"]:
        raise ValueError("unsupported entry signature")
    steps = program["steps"]
    if [step["value"] for step in steps] != ["left", "right"] or any(
        type(step["tag"]) is not int or not 0 <= step["tag"] <= 63 for step in steps
    ):
        raise ValueError("unsupported steps")
    lines = [
        '#include "abi.h"',
        "",
        "struct result emit_pair(struct runtime *runtime, int32_t left, int32_t right) {",
    ]
    for step in reversed(steps) if reverse else steps:
        lines.extend([
            f"    if (rt_emit(runtime, {step['tag']}, {step['value']}) != ACCEPTED) {{",
            "        return (struct result){QUOTA_EXHAUSTED, NO_RESULT};",
            "    }",
        ])
    lines.extend(["    return (struct result){ACCEPTED, left + right};", "}", ""])
    return "\n".join(lines)


if __name__ == "__main__":
    source = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    sys.stdout.write(emit(source, reverse=sys.argv[2:] == ["--reverse"]))
