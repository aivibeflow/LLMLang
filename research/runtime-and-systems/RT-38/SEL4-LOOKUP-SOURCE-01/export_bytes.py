"""Insert the exact stored source bytes as HOL numerals without parsing the language."""
import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCES = (
    "direct", "renamed-refactor", "swapped-result", "aliased-registers",
    "reordered-steps", "unsupported-operation", "missing-line-end",
)


def generate():
    template = (HERE / "SourceLookup.thy.in").read_text(encoding="utf-8")
    for name in SOURCES:
        marker = "@" + name.replace("-", "_").upper() + "@"
        if template.count(marker) != 1:
            raise ValueError(f"Expected one source marker for {name}")
        data = (HERE / "sources" / f"{name}.ops").read_bytes()
        template = template.replace(marker, "[" + ", ".join(map(str, data)) + "]")
    return template


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(generate(), encoding="utf-8")
