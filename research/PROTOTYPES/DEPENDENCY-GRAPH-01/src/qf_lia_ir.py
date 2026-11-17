"""Typed canonical relational-query IR and deterministic QF_LIA SMT-LIB renderer."""
from __future__ import annotations
from dataclasses import dataclass
import re
from typing import Any
from .formal_core import UnsupportedConstruct

@dataclass(frozen=True)
class Term:
    op: str
    sort: str
    args: tuple["Term", ...] = ()
    atom: Any = None

@dataclass(frozen=True)
class Declaration:
    name: str
    sort: str

@dataclass(frozen=True)
class RelationalQuery:
    factor: str
    declarations: tuple[Declaration, ...]
    factor_difference: Term
    observations_differ: Term
    observation_contract: str = "return-and-selected-state/1"


def _validate_term(term: Term, declarations: dict[str, str]) -> str:
    if not isinstance(term, Term): raise UnsupportedConstruct("query contains a non-Term node")
    if term.op == "bool":
        if term.sort != "Bool" or term.args or type(term.atom) is not bool: raise UnsupportedConstruct("invalid Boolean literal")
        return "Bool"
    if term.op == "int":
        if term.sort != "Int" or term.args or type(term.atom) is not int: raise UnsupportedConstruct("invalid integer literal")
        return "Int"
    if term.op == "symbol":
        if term.args or not isinstance(term.atom, str) or term.atom not in declarations or declarations[term.atom] != term.sort:
            raise UnsupportedConstruct("undeclared or ill-sorted query symbol")
        return term.sort
    child_sorts = tuple(_validate_term(child, declarations) for child in term.args)
    if term.op == "not" and term.sort == "Bool" and child_sorts == ("Bool",): return "Bool"
    if term.op == "neg" and term.sort == "Int" and child_sorts == ("Int",): return "Int"
    if term.op in ("add", "sub") and term.sort == "Int" and child_sorts == ("Int", "Int"): return "Int"
    if term.op == "mul" and term.sort == "Int" and child_sorts == ("Int", "Int"):
        if not any(child.op == "int" for child in term.args): raise UnsupportedConstruct("nonlinear multiplication in query IR")
        return "Int"
    if term.op == "eq" and term.sort == "Bool" and len(child_sorts) == 2 and child_sorts[0] == child_sorts[1] and child_sorts[0] in ("Int", "Bool"):
        return "Bool"
    if term.op in ("lt", "le") and term.sort == "Bool" and child_sorts == ("Int", "Int"): return "Bool"
    if term.op in ("and", "or") and term.sort == "Bool" and len(child_sorts) >= 2 and all(s == "Bool" for s in child_sorts): return "Bool"
    if term.op == "ite" and len(child_sorts) == 3 and child_sorts[0] == "Bool" and child_sorts[1] == child_sorts[2] == term.sort:
        return term.sort
    raise UnsupportedConstruct(f"unsupported or ill-typed QF_LIA term: {term.op}/{term.sort}")


def render_term(term: Term) -> str:
    if term.op == "bool": return "true" if term.atom else "false"
    if term.op == "int": return str(term.atom) if term.atom >= 0 else f"(- {abs(term.atom)})"
    if term.op == "symbol": return term.atom
    rendered = tuple(render_term(x) for x in term.args)
    if term.op == "not": return f"(not {rendered[0]})"
    if term.op == "neg": return f"(- {rendered[0]})"
    if term.op in ("add", "sub", "mul", "eq", "lt", "le", "and", "or"):
        op = {"add": "+", "sub": "-", "mul": "*", "eq": "=", "lt": "<", "le": "<="}.get(term.op, term.op)
        return f"({op} {' '.join(rendered)})"
    if term.op == "ite": return f"(ite {rendered[0]} {rendered[1]} {rendered[2]})"
    raise UnsupportedConstruct(f"cannot render term operator: {term.op}")


def render_smt2(query: RelationalQuery) -> str:
    if not isinstance(query, RelationalQuery): raise UnsupportedConstruct("expected RelationalQuery")
    if not isinstance(query.factor, str) or not query.factor: raise UnsupportedConstruct("query factor is required")
    if not query.observation_contract: raise UnsupportedConstruct("observation contract is required")
    symbols: dict[str, str] = {}
    for decl in query.declarations:
        if (not isinstance(decl.name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", decl.name)
                or decl.sort not in ("Int", "Bool") or decl.name in symbols):
            raise UnsupportedConstruct("invalid or duplicate QF_LIA declaration")
        symbols[decl.name] = decl.sort
    if _validate_term(query.factor_difference, symbols) != "Bool": raise UnsupportedConstruct("factor constraint must be Boolean")
    if _validate_term(query.observations_differ, symbols) != "Bool": raise UnsupportedConstruct("observation constraint must be Boolean")
    lines = ["(set-logic QF_LIA)"]
    lines.extend(f"(declare-const {d.name} {d.sort})" for d in query.declarations)
    lines.append(f"(assert {render_term(query.factor_difference)})")
    lines.append(f"(assert {render_term(query.observations_differ)})")
    lines.append("(check-sat)")
    return "\n".join(lines) + "\n"
