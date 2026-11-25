"""Exercise field-scoped provenance with exact source spans and decisions."""

from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path
import platform
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PROTOTYPE = ROOT / "research/PROTOTYPES/DEPENDENCY-GRAPH-01"
CORPUS = HERE.parent / "RECONSTRUCTION-ROUNDTRIP-01/corpus.json"
sys.path.insert(0, str(PROTOTYPE))
from src.semantic_graph import digest


@dataclass(frozen=True)
class Interpretation:
    source: str
    revision: str
    start: int
    end: int
    quote: str
    scope: str
    field: str
    value: str
    authority: str
    supersedes: str | None = None

    @property
    def identity(self):
        return digest({"kind": "rt02-source-interpretation", **asdict(self)})

    @property
    def subject(self):
        return self.scope, self.field


def document_key(text):
    return digest({"kind": "rt02-source", "text": text})


def interpret(sources, source, quote, field, value, *, authority="stakeholder", supersedes=None):
    document = sources[source]
    start = document.index(quote)
    return Interpretation(source, document_key(document), start, start + len(quote), quote,
                          "retail", field, value, authority, supersedes)


def source_problem(sources, record):
    document = sources.get(record.source)
    if document is None:
        return "DANGLING_SOURCE"
    if document_key(document) != record.revision:
        return "STALE_SOURCE_REVISION"
    if not (0 <= record.start < record.end <= len(document)) or document[record.start:record.end] != record.quote:
        return "INVALID_SPAN"
    if record.authority != "stakeholder":
        return "UNAUTHORIZED"
    return None


def check(sources, catalog, selected, references, subject, expected):
    """Check typed attestations supplied by the fixture, without interpreting prose."""
    if any(ref not in catalog for ref in (*selected, *references)):
        return "DANGLING_REFERENCE"

    used = {key: catalog[key] for key in (*selected, *references)}
    for record in used.values():
        if problem := source_problem(sources, record):
            return problem
        if record.supersedes:
            earlier = catalog.get(record.supersedes)
            if (earlier is None or earlier.subject != record.subject or record.supersedes not in selected
                    or source_problem(sources, earlier)):
                return "INVALID_SUPERSESSION"

    superseded = {catalog[key].supersedes for key in selected} - {None}
    current = {key for key in selected if key not in superseded and catalog[key].subject == subject}
    values = {catalog[key].value for key in current}
    if len(values) > 1:
        return "CONFLICT"
    if not references or not set(references) <= current or values != {expected}:
        return "UNSUPPORTED"
    return "SUPPORTED"


def clause_key(kind, clause, parent=None):
    return digest({"kind": kind, "clause": clause, "parent": parent})


def trace(ir, formal, rendered, formal_parent, render_parent):
    if formal_parent != clause_key("ir", ir) or render_parent != clause_key("formal", formal, formal_parent):
        return "STALE_CLAUSE_BINDING"
    return "SUPPORTED" if ir == formal == rendered else "INTERPRETATION_MISMATCH"


def main():
    sources = json.loads(CORPUS.read_text())["source_fragments"]
    base = interpret(sources, "clock", "Use payment registration as the clock origin.",
                     "clock-origin", "payment registration")
    copy = interpret(sources, "clock-copy", "use payment registration", "clock-origin", "payment registration")
    alternate = interpret(sources, "conflicting-clock", "use reservation completion as clock origin",
                          "clock-origin", "reservation completion")
    unauthorized = replace(alternate, authority="proposal-agent")
    adopted = replace(alternate, supersedes=base.identity)
    wrong_scope_replacement = replace(adopted, scope="wholesale")
    wrong_field = interpret(sources, "operator", "the automatic order-status transition",
                            "action", "automatic confirmation")
    broken_span = replace(base, end=base.end + 1)
    missing_source = replace(base, source="missing-source")
    catalog = {r.identity: r for r in (base, copy, alternate, unauthorized, adopted, wrong_scope_replacement,
                                      wrong_field, broken_span, missing_source)}
    stale = sources | {"clock": sources["clock"] + " Source revision changed."}
    cases = {
        "exact_span": (sources, (base,), (base,), base.value, "SUPPORTED"),
        "equivalent_attestations": (sources, (base, copy), (copy,), base.value, "SUPPORTED"),
        "wrong_value": (sources, (base,), (base,), alternate.value, "UNSUPPORTED"),
        "wrong_field": (sources, (base, wrong_field), (wrong_field,), base.value, "UNSUPPORTED"),
        "dangling_reference": (sources, (base,), ("missing",), base.value, "DANGLING_REFERENCE"),
        "dangling_source": (sources, (missing_source,), (missing_source,), base.value, "DANGLING_SOURCE"),
        "stale_source_revision": (stale, (base,), (base,), base.value, "STALE_SOURCE_REVISION"),
        "incorrect_span": (sources, (broken_span,), (broken_span,), base.value, "INVALID_SPAN"),
        "unauthorized_clarification": (sources, (base, unauthorized), (unauthorized,), alternate.value,
                                       "UNAUTHORIZED"),
        "contradiction_not_cited_by_clause": (sources, (base, alternate), (base,), base.value, "CONFLICT"),
        "authorized_replacement": (sources, (base, adopted), (adopted,), alternate.value, "SUPPORTED"),
        "use_replaced_decision": (sources, (base, adopted), (base,), base.value, "UNSUPPORTED"),
        "mixed_active_and_replaced_support": (sources, (base, adopted), (base, adopted), alternate.value,
                                              "UNSUPPORTED"),
        "out_of_scope_replacement": (sources, (base, wrong_scope_replacement), (base,), base.value,
                                     "INVALID_SUPERSESSION"),
    }
    results = {}
    for name, (snapshot, selection, refs, value, expected) in cases.items():
        selected = tuple(item.identity for item in selection)
        references = tuple(item if isinstance(item, str) else item.identity for item in refs)
        actual = check(snapshot, catalog, selected, references, base.subject, value)
        assert actual == expected, (name, actual, expected)
        results[name] = {"selected": selected, "references": references, "requested_value": value,
                         "status": actual}

    original = {"scope": base.scope, "field": base.field, "value": base.value}
    mutation = original | {"value": alternate.value}
    ir = clause_key("ir", original)
    formal = clause_key("formal", original, ir)
    revised_formal = clause_key("formal", mutation, ir)
    dispositions = {
        "exact_typed_chain": trace(original, original, original, ir, formal),
        "stale_formal_edge": trace(mutation, original, original, ir, formal),
        "stale_render_edge": trace(original, mutation, original, ir, formal),
        "formal_changes_meaning": trace(original, mutation, mutation, ir, revised_formal),
        "render_changes_meaning": trace(original, original, mutation, ir, formal),
    }
    assert list(dispositions.values()) == ["SUPPORTED", "STALE_CLAUSE_BINDING", "STALE_CLAUSE_BINDING",
                                            "INTERPRETATION_MISMATCH", "INTERPRETATION_MISMATCH"]
    paths = (Path(__file__), CORPUS, PROTOTYPE / "src/semantic_graph.py")
    return {"schema": "llmlang-rt02-clause-provenance/1", "python": platform.python_version(),
            "source_sha256": {str(p.resolve().relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in paths},
            "interpretations": {key: asdict(record) for key, record in catalog.items()},
            "source_controls": results, "typed_chain_controls": dispositions}


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
