"""Fixture checker for an exact bound on an integer closed walk."""

from dataclasses import asdict, dataclass
from hashlib import sha256
import json

from rt03_feasibility_outcomes import SolverAnswer, classify_solver_answer, retain_as_possible


@dataclass(frozen=True)
class Edge:
    source: int
    destination: int
    bound: int
    premise_revision: str


@dataclass(frozen=True)
class Query:
    route_revision: str
    profile: str
    variable_count: int
    constraints: tuple[Edge, ...]

    def formula(self):
        if type(self.variable_count) is not int or self.variable_count < 1:
            raise ValueError("invalid variable count")
        lines = ["(set-logic QF_LIA)"]
        lines.extend(f"(declare-const x{i} Int)" for i in range(self.variable_count))
        for edge in self.constraints:
            if (type(edge.source) is not int or not 0 <= edge.source < self.variable_count
                    or type(edge.destination) is not int or not 0 <= edge.destination < self.variable_count
                    or type(edge.bound) is not int):
                raise ValueError("invalid difference constraint")
            bound = str(edge.bound) if edge.bound >= 0 else f"(- {-edge.bound})"
            lines.append(f"(assert (<= (- x{edge.destination} x{edge.source}) {bound}))")
        return "\n".join([*lines, "(check-sat)", ""])

    @property
    def identity(self):
        formula_hash = sha256(self.formula().encode()).hexdigest()
        body = {"scheme": "rt03-difference-query-v1", "route": asdict(self), "formula": formula_hash}
        return sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class Certificate:
    query_identity: str
    edges: tuple[int, ...]


def checked_negative_walk(query, certificate):
    if query.profile != "integer-difference-v1" or certificate.query_identity != query.identity:
        return False
    if not certificate.edges or len(certificate.edges) > len(query.constraints):
        return False
    if any(type(index) is not int or not 0 <= index < len(query.constraints) for index in certificate.edges):
        return False
    walk = [query.constraints[index] for index in certificate.edges]
    return (sum(edge.bound for edge in walk) < 0
            and all(before.destination == after.source for before, after in zip(walk, walk[1:] + walk[:1])))


def classify(query, status, certificate=None):
    exact_certificate = (
        status == "unsat" and certificate is not None and checked_negative_walk(query, certificate)
    )
    answer = SolverAnswer(status, unsat_basis="checked_certificate" if exact_certificate else None)
    verdict = classify_solver_answer(answer, (), frozenset())
    return verdict.value, retain_as_possible(verdict)
