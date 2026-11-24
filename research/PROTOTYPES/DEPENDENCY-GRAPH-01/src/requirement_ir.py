"""Typed, finite-domain Requirement IR research prototype.

This module deliberately does not parse natural language. It validates an explicitly
constructed IR, checks finite-domain consistency, emits finite scenarios, and checks
caller-policy / callee-capability separation.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from itertools import product
from typing import Any, Iterable, Mapping


class RequirementIRError(ValueError):
    pass


class ValueType(str, Enum):
    BOOL = "bool"
    INT = "int"
    TEXT = "text"


class Operator(str, Enum):
    EQ = "eq"
    NE = "ne"
    LT = "lt"
    LE = "le"
    GT = "gt"
    GE = "ge"


@dataclass(frozen=True)
class Variable:
    name: str
    value_type: ValueType
    domain: tuple[Any, ...]

    def __post_init__(self) -> None:
        if not self.name or not self.domain:
            raise RequirementIRError("variable needs a name and a finite non-empty domain")
        if len(set(self.domain)) != len(self.domain):
            raise RequirementIRError(f"duplicate values in domain for {self.name}")
        for value in self.domain:
            if not _matches_type(value, self.value_type):
                raise RequirementIRError(f"domain value has wrong type for {self.name}")


@dataclass(frozen=True)
class Predicate:
    variable: str
    operator: Operator
    value: Any


@dataclass(frozen=True)
class Junction:
    operator: str
    terms: tuple["Expression", ...]

    def __post_init__(self) -> None:
        if self.operator not in {"and", "or"} or not self.terms:
            raise RequirementIRError("junction must be non-empty and use and/or")


@dataclass(frozen=True)
class Negation:
    term: "Expression"


Expression = Predicate | Junction | Negation


@dataclass(frozen=True)
class Trigger:
    event: str
    condition: Expression | None = None


@dataclass(frozen=True)
class Action:
    operation: str
    target: str
    arguments: tuple[tuple[str, Any], ...] = ()


@dataclass(frozen=True)
class TemporalBound:
    relation: str
    amount: int
    unit: str

    def __post_init__(self) -> None:
        if self.relation not in {"within", "after", "before", "until"}:
            raise RequirementIRError("unsupported temporal relation")
        if self.amount < 0 or not self.unit:
            raise RequirementIRError("temporal bound needs non-negative amount and unit")


@dataclass(frozen=True)
class Requirement:
    requirement_id: str
    owner: str
    scope: str
    constraint: Expression
    source_refs: tuple[str, ...]
    decision_refs: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    unresolved: tuple[str, ...] = ()
    required_dimensions: tuple[str, ...] = ()
    trigger: Trigger | None = None
    action: Action | None = None
    temporal: TemporalBound | None = None

    def __post_init__(self) -> None:
        if not self.requirement_id or not self.owner or not self.scope:
            raise RequirementIRError("requirement id, owner, and scope are mandatory")
        if not self.source_refs and not self.decision_refs:
            raise RequirementIRError("requirement needs source or decision provenance")


@dataclass(frozen=True)
class RequirementIR:
    variables: tuple[Variable, ...]
    requirements: tuple[Requirement, ...]
    source_ids: frozenset[str]
    decision_ids: frozenset[str]

    def __post_init__(self) -> None:
        names = [v.name for v in self.variables]
        ids = [r.requirement_id for r in self.requirements]
        if len(names) != len(set(names)):
            raise RequirementIRError("variable names must be unique")
        if len(ids) != len(set(ids)):
            raise RequirementIRError("requirement ids must be unique")


@dataclass(frozen=True)
class Issue:
    code: str
    subject: str
    message: str


@dataclass(frozen=True)
class Scenario:
    values: tuple[tuple[str, Any], ...]
    satisfies: bool
    violated_requirements: tuple[str, ...]


@dataclass(frozen=True)
class Analysis:
    issues: tuple[Issue, ...]
    scenarios: tuple[Scenario, ...]
    status: str


@dataclass(frozen=True)
class BusinessRule:
    rule_id: str
    owner_component: str
    scope: str
    expression: Expression
    source_refs: tuple[str, ...]


@dataclass(frozen=True)
class ComponentContract:
    component: str
    role: str
    policy_inputs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.role not in {"caller", "callee"}:
            raise RequirementIRError("component role must be caller or callee")


def _matches_type(value: Any, value_type: ValueType) -> bool:
    if value_type is ValueType.BOOL:
        return type(value) is bool
    if value_type is ValueType.INT:
        return type(value) is int
    if value_type is ValueType.TEXT:
        return isinstance(value, str)
    return False


def _validate_expression(expr: Expression, variables: Mapping[str, Variable],
                         issues: list[Issue], subject: str) -> set[str]:
    if isinstance(expr, Predicate):
        variable = variables.get(expr.variable)
        if variable is None:
            issues.append(Issue("UNKNOWN_VARIABLE", subject,
                                f"unknown variable {expr.variable}"))
            return {expr.variable}
        if not _matches_type(expr.value, variable.value_type):
            issues.append(Issue("TYPE_MISMATCH", subject,
                                f"literal for {expr.variable} is not {variable.value_type.value}"))
        if expr.operator in {Operator.LT, Operator.LE, Operator.GT, Operator.GE}:
            if variable.value_type not in {ValueType.INT}:
                issues.append(Issue("INVALID_OPERATOR", subject,
                                    f"ordered comparison is unsupported for {variable.value_type.value}"))
        return {expr.variable}
    if isinstance(expr, Junction):
        found: set[str] = set()
        for term in expr.terms:
            found |= _validate_expression(term, variables, issues, subject)
        return found
    if isinstance(expr, Negation):
        return _validate_expression(expr.term, variables, issues, subject)
    issues.append(Issue("INVALID_EXPRESSION", subject, "unsupported expression node"))
    return set()


def evaluate(expr: Expression, values: Mapping[str, Any]) -> bool:
    if isinstance(expr, Predicate):
        left = values[expr.variable]
        right = expr.value
        return {
            Operator.EQ: lambda: left == right,
            Operator.NE: lambda: left != right,
            Operator.LT: lambda: left < right,
            Operator.LE: lambda: left <= right,
            Operator.GT: lambda: left > right,
            Operator.GE: lambda: left >= right,
        }[expr.operator]()
    if isinstance(expr, Junction):
        checks = (evaluate(term, values) for term in expr.terms)
        return all(checks) if expr.operator == "and" else any(checks)
    if isinstance(expr, Negation):
        return not evaluate(expr.term, values)
    raise RequirementIRError("unsupported expression node")


def _assignments(variables: tuple[Variable, ...], limit: int) -> Iterable[dict[str, Any]] | None:
    count = 1
    for variable in variables:
        count *= len(variable.domain)
    if count > limit:
        return None
    names = [v.name for v in variables]
    return (dict(zip(names, values)) for values in product(*(v.domain for v in variables)))


def analyze(ir: RequirementIR, max_assignments: int = 10_000) -> Analysis:
    issues: list[Issue] = []
    variable_map = {v.name: v for v in ir.variables}
    for req in ir.requirements:
        missing_sources = set(req.source_refs) - ir.source_ids
        missing_decisions = set(req.decision_refs) - ir.decision_ids
        if missing_sources or missing_decisions:
            issues.append(Issue("DANGLING_PROVENANCE", req.requirement_id,
                                f"unknown source refs {sorted(missing_sources)}; "
                                f"unknown decision refs {sorted(missing_decisions)}"))
        used = _validate_expression(req.constraint, variable_map, issues, req.requirement_id)
        if req.trigger and req.trigger.condition:
            used |= _validate_expression(req.trigger.condition, variable_map, issues,
                                          req.requirement_id + ":trigger")
        if req.unresolved:
            issues.append(Issue("UNRESOLVED", req.requirement_id,
                                "; ".join(req.unresolved)))
        if req.assumptions:
            issues.append(Issue("ASSUMPTION", req.requirement_id,
                                "; ".join(req.assumptions)))
        for dimension in req.required_dimensions:
            if dimension not in variable_map:
                issues.append(Issue("UNKNOWN_DIMENSION", req.requirement_id, dimension))
    if any(i.code in {"UNKNOWN_VARIABLE", "TYPE_MISMATCH", "INVALID_OPERATOR",
                      "INVALID_EXPRESSION", "UNKNOWN_DIMENSION"} for i in issues):
        return Analysis(tuple(issues), (), "INVALID")

    assignment_rows = _assignments(ir.variables, max_assignments)
    if assignment_rows is None:
        issues.append(Issue("ANALYSIS_BOUND_EXCEEDED", "project",
                            f"finite state space exceeds {max_assignments} assignments"))
        return Analysis(tuple(issues), (), "UNKNOWN")
    assignments = tuple(assignment_rows)

    scenarios: list[Scenario] = []
    by_scope: dict[str, list[Requirement]] = {}
    for req in ir.requirements:
        by_scope.setdefault(req.scope, []).append(req)

    for scope, requirements in by_scope.items():
        satisfying: list[dict[str, Any]] = []
        for values in assignments:
            failed = tuple(req.requirement_id for req in requirements
                           if not evaluate(req.constraint, values))
            scenarios.append(Scenario(tuple(sorted(values.items())), not failed, failed))
            if not failed:
                satisfying.append(values)
        if not satisfying:
            issues.append(Issue("CONTRADICTION", scope,
                                "no assignment satisfies all constraints in this scope"))
            continue
        for req in requirements:
            for dimension in req.required_dimensions:
                possible = {row[dimension] for row in satisfying}
                if len(possible) > 1:
                    issues.append(Issue("UNDERDETERMINED", req.requirement_id,
                                        f"{dimension} has multiple allowed values: "
                                        f"{sorted(possible, key=repr)}"))

    if any(i.code in {"CONTRADICTION", "UNDERDETERMINED", "UNRESOLVED",
                      "DANGLING_PROVENANCE", "ASSUMPTION"} for i in issues):
        status = "NEEDS_REVIEW"
    else:
        status = "FINITE_MODEL_CONSISTENT"
    return Analysis(tuple(issues), tuple(scenarios), status)


def validate_policy_boundary(rule: BusinessRule, caller: ComponentContract,
                             callee: ComponentContract,
                             required_policy_input: str = "rate_basis_points") -> tuple[Issue, ...]:
    issues: list[Issue] = []
    if caller.role != "caller" or callee.role != "callee":
        return (Issue("INVALID_COMPONENT_ROLES", rule.rule_id,
                      "policy boundary expects caller then callee"),)
    if rule.owner_component != caller.component:
        issues.append(Issue("POLICY_OWNER_MISMATCH", rule.rule_id,
                            "caller-local business rule is not owned by its caller"))
    if rule.owner_component == callee.component:
        issues.append(Issue("HIDDEN_CALLEE_POLICY", rule.rule_id,
                            "caller business policy is embedded in the generic callee"))
    if required_policy_input not in callee.policy_inputs:
        issues.append(Issue("MISSING_POLICY_INPUT", callee.component,
                            f"callee must accept explicit {required_policy_input} input"))
    return tuple(issues)


def generate_scenarios(ir: RequirementIR, max_assignments: int = 10_000) -> tuple[Scenario, ...]:
    """Return exhaustive finite assignments labelled by satisfied requirements."""
    return analyze(ir, max_assignments=max_assignments).scenarios
