"""Versioned textconv for the closed program declaration used in RT-24."""

import json
import sys
from pathlib import Path

VERSION = "llmlang-review/v1"


def project(data):
    declaration = json.loads(data)
    if (
        set(declaration) != {"binding", "entry"}
        or declaration["binding"] not in {"plus", "minus"}
        or not isinstance(declaration["entry"], str)
    ):
        raise ValueError("unsupported program declaration")
    entry = json.dumps(declaration["entry"], ensure_ascii=True)
    return f"{VERSION}\ncompute provider {declaration['binding']}\nentry {entry}\n"


if __name__ == "__main__":
    print(project(Path(sys.argv[1]).read_bytes()), end="")
