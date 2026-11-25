"""Compare direct graph and normalized code while checking hybrid source receipts."""

from collections import Counter
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
RT13 = HERE.parents[1] / "RT-13"
CORPUS = RT13 / "GENERATED-GO-INTEGERS-01"
PYTHON = RT13 / "GENERATED-PYTHON-INTEGERS-01"
sys.path[:0] = [str(CORPUS), str(PYTHON)]
from run import FIXTURE, SENTINEL, reference, source, vectors
from lower_python import lower
from integer_fixture import WRAPPING, compile_source
from llvm_integer_probe import _STATUS


OPERATORS = {"wrap_add": "+", "wrap_sub": "-", "wrap_mul": "*"}
FORMATS = (
    (("first", "second"), "src/calc-a", 20),
    (("value_left", "value_right"), "src/calc-a", 40),
    (("lhs", "rhs"), "src/new-name", 7),
    (("x", "y"), "src/explicit", 110),
)
ROLES = ("argument-event", "calculation", "result-event", "write-slot")


@dataclass(frozen=True)
class Graph:
    params: tuple[str, str]
    op: str
    operands: tuple[str, str]
    document: str
    lines: tuple[int, ...]
    source_revision: str


@dataclass(frozen=True)
class OriginReceipt:
    semantic_program: str
    source_document: str
    source_revision: str
    locations: tuple[tuple[str, int], ...]


def digest(data):
    return sha256(data).hexdigest()


def stable(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def variants(program):
    for params, document, first_line in FORMATS:
        aliases = dict(zip("ab", params, strict=True))
        operands = tuple(aliases[operand] for operand in program.operands)
        revision = digest(stable([params, program.operation, operands, document, first_line]))
        yield Graph(params, program.operation, operands, document,
                    (first_line, first_line + 2, first_line + 3, first_line + 4), revision)


def project(graph):
    bindings = dict(zip(graph.params, "ab", strict=True))
    left, right = (bindings[name] for name in graph.operands)
    return compile_source(source(graph.op, left, right))


def lowered_direct(graph):
    first, second = graph.params
    left, right = graph.operands
    operation = OPERATORS[graph.op]
    return f"""def probe_0({first}, {second}, enabled, emit, slot):
    emit({first})
    value = {second}
    if enabled:
        value = ({left} {operation} {right}) & 0xffffffff
    emit(value)
    slot[0] = value
    return 0
"""


def origin_receipt(graph, program):
    return OriginReceipt(digest(stable(asdict(program))), graph.document, graph.source_revision,
                         tuple(zip(ROLES, graph.lines, strict=True)))


def exact_origin(graph, program, receipt):
    return origin_receipt(graph, program) == receipt


def load(source_text):
    program = {}
    exec(compile(source_text, "<checked-generated-lowering>", "exec"), program)
    return program["probe_0"]


def runtime(code, inputs, expected):
    result = []
    for vector, wanted in zip(inputs, expected, strict=True):
        events = []
        slot = [SENTINEL]
        status = code(*vector, events.append, slot)
        actual = (_STATUS[status], slot[0], tuple(events))
        if actual != wanted:
            raise AssertionError((vector, wanted, actual))
        result.append(actual)
    return digest(stable(result))


def tally():
    references = tuple(compile_source(source(operation, left, right))
                       for operation, (left, right) in product(WRAPPING, product("ab", repeat=2)))
    inputs = vectors()
    graphs = []
    direct_artifacts = set()
    normalized_artifacts = set()
    observations = Counter()
    trace_hashes = {}

    for program in references:
        expected = tuple(reference(program, vector) for vector in inputs)
        for graph in variants(program):
            typed = project(graph)
            if typed != program:
                raise AssertionError((typed, program))
            direct = lowered_direct(graph)
            normalized = lower((typed,))
            receipt = origin_receipt(graph, typed)
            if not exact_origin(graph, typed, receipt):
                raise AssertionError("Fresh receipt failed exact origin")
            direct_artifacts.add(digest(direct.encode()))
            normalized_artifacts.add(digest(normalized.encode()))
            route_digests = set()
            for label, code in (("direct", direct), ("normalized", normalized), ("hybrid", normalized)):
                route_digests.add(runtime(load(code), inputs, expected))
                observations[label] += len(inputs)
            if len(route_digests) != 1:
                raise AssertionError("Translation routes disagree")
            graph_id = digest(stable(asdict(graph)))
            trace_hashes[graph_id] = route_digests.pop()
            graphs.append((graph, typed, receipt))

    scope = Counter()
    for (left_index, (graph, program, current)), (right_index, (_, _, swapped)) in product(
        enumerate(graphs), repeat=2
    ):
        weak = current.semantic_program == swapped.semantic_program
        exact = exact_origin(graph, program, swapped)
        if exact != (left_index == right_index):
            raise AssertionError("Unexpected source receipt classification")
        scope["transplants"] += 1
        scope["exact_accept"] += exact
        scope["semantic_only_accept"] += weak
        scope["wrong_origins_with_semantic_only"] += weak and not exact

    graph, program, authentic = graphs[0]
    changed_location = replace(authentic, locations=((ROLES[0], graph.lines[0] + 1), *authentic.locations[1:]))
    assert changed_location.semantic_program == authentic.semantic_program
    assert not exact_origin(graph, program, changed_location)
    control = lowered_direct(graph)
    wrong_order = control.replace("    emit(first)\n", "").replace("    emit(value)\n",
                                                                   "    emit(value)\n    emit(first)\n")
    witness = (7, 2, 1)
    expected = reference(program, witness)
    actual_events = []
    output = [SENTINEL]
    actual_status = load(wrong_order)(*witness, actual_events.append, output)
    assert (_STATUS[actual_status], output[0], tuple(reversed(actual_events))) == expected
    assert tuple(actual_events) != expected[2]
    source_paths = (HERE / "run.py", CORPUS / "run.py", PYTHON / "lower_python.py",
                    FIXTURE / "integer_fixture.py", FIXTURE / "llvm_integer_probe.py")
    return {
        "graphs": len(graphs),
        "direct_generated_source_count": len(direct_artifacts),
        "shared_generated_source_count": len(normalized_artifacts),
        "runtime_observations": observations,
        "origin_admission_counts": scope,
        "location_change_with_exact_source_label_refused": True,
        "reordered_event_control": {"expected": expected[2], "observed": actual_events},
        "source_sha256": {path.relative_to(HERE.parents[3]).as_posix(): digest(path.read_bytes())
                          for path in source_paths},
        "trace_hashes_by_source_graph": trace_hashes,
    }


if __name__ == "__main__":
    print(json.dumps(tally(), indent=2))
