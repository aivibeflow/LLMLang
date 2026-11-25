"""Render the supported typed copy contract and loop obligations into Dafny."""

import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
SCHEMA = "llmlang-candidate-copy-frame/1"
PROFILES = {
    "short": {"a": "a", "src": "src", "dst": "dst", "len": "len"},
    "named": {"a": "buffer", "src": "origin", "dst": "target", "len": "count"},
}
REQUIRES = {
    "source-in-bounds": "src + len <= a.Length",
    "target-in-bounds": "dst + len <= a.Length",
    "safe-forward-order": "dst <= src || src + len <= dst",
}
POSTS = {"target-from-old-source", "outside-target-unchanged"}
LOOPS = {
    ("processed-prefix", "remaining-length"): ("dst <= i < dst + n", "len - n"),
    ("processed-suffix", "remaining-prefix"): ("dst + n <= i < dst + len", "n"),
}
PLACEHOLDER = re.compile(r"^( +)@(CONTRACT|LOOP)\(([a-z]+)\)$", re.MULTILINE)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def require(condition, problem):
    if not condition:
        raise ValueError(problem)


def validate(graph):
    require(graph.get("schema") == SCHEMA, "unsupported graph schema")
    require(set(graph) == {"schema", "parameters", "spans", "contracts", "effects", "loops", "assumptions"},
            "unsupported graph fields")
    require(graph["parameters"] == {"array": "MutableArray<Int>", "source": "Nat",
                                     "target": "Nat", "length": "Nat"}, "unsupported typed inputs")
    require(graph["spans"] == {
        role: {"object": "array", "start": role, "size": "length"} for role in ("source", "target")
    }, "unsupported span identity")
    require(graph["effects"] == {"read_span": "source", "write_span": "target"}, "unsupported effect footprint")
    require(graph["assumptions"] == ["sequential-no-external-writer", "unbounded-integer-values"],
            "unsupported assumptions")
    require(set(graph["contracts"]) == {"full", "forward", "weak"}, "unsupported contract names")
    for contract in graph["contracts"].values():
        require(set(contract) == {"requires", "modifies", "ensures"}, "unsupported contract fields")
        required, ensured = contract["requires"], contract["ensures"]
        require(set(required) <= REQUIRES.keys() and len(required) == len(set(required))
                and {"source-in-bounds", "target-in-bounds"} <= set(required), "unsupported preconditions")
        require(set(ensured) <= POSTS and len(ensured) == len(set(ensured))
                and "target-from-old-source" in ensured, "unsupported postconditions")
        require(contract["modifies"] == "array", "unsupported heap frame")
    require(set(graph["loops"]) == {"forward", "backward"}, "unsupported loop directions")
    for name, shape in graph["loops"].items():
        require(set(shape) == {"range", "decreases"}, "unsupported loop clauses")
        key = (shape["range"], shape["decreases"])
        require(key in LOOPS, "unsupported loop invariant or variant")
        require(key[0] == ("processed-prefix" if name == "forward" else "processed-suffix"),
                "loop clauses apply to a different direction")


def contract_lines(contract):
    order = sorted(contract["requires"])
    lines = [f"requires {REQUIRES[condition]}" for condition in order]
    lines.append("modifies a")
    if "outside-target-unchanged" in contract["ensures"]:
        lines.extend((
            "ensures forall i {:trigger a[i]} | 0 <= i < a.Length ::",
            "  a[i] == (if dst <= i < dst + len then old(a[..])[src + i - dst] else old(a[..])[i])",
        ))
    else:
        lines.append("ensures forall i {:trigger a[i]} | dst <= i < dst + len :: a[i] == old(a[..])[src + i - dst]")
    return lines


def loop_lines(graph, variant):
    loop = graph["loops"]["forward" if variant == "snapshot" else variant]
    range_test, measure = LOOPS[(loop["range"], loop["decreases"])]
    lines = ["invariant before == old(a[..])", "invariant 0 <= n <= len"]
    if variant == "snapshot":
        lines.append("invariant saved == before[src..src + len]")
    lines.extend((
        "invariant forall i {:trigger a[i]} | 0 <= i < a.Length ::",
        f"  a[i] == (if {range_test} then before[src + i - dst] else before[i])",
        f"decreases {measure}",
    ))
    return lines


def render(graph, profile):
    validate(graph)

    def insert(match):
        indent, kind, key = match.groups()
        lines = (contract_lines(graph["contracts"][key]) if kind == "CONTRACT"
                 else loop_lines(graph, key))
        return "\n".join(indent + line for line in lines)

    template = (HERE / "copy.dfy.in").read_text(encoding="utf-8")
    program = PLACEHOLDER.sub(insert, template)
    require("@" not in program, "unresolved template clause")
    names = PROFILES[profile]
    return re.sub(r"\b(a|src|dst|len)\b", lambda token: names[token.group(0)], program)


if __name__ == "__main__":
    graph = json.loads((HERE / "graph.json").read_text(encoding="utf-8"))
    print(render(graph, "short"), end="")
