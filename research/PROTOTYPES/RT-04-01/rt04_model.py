"""Small executable comparison of two RT-04 design vectors.
This is a finite declaration-level checker model, not a parser or LLMLang compiler.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

class ModelError(ValueError):
    pass

@dataclass(frozen=True)
class Finding:
    code: str
    subject: str
    detail: str

@dataclass(frozen=True)
class CheckResult:
    profile: str
    status: str
    findings: tuple[Finding, ...]
    inferred_effects: tuple[tuple[str, tuple[str, ...]], ...]
    inferred_capabilities: tuple[tuple[str, tuple[str, ...]], ...]

    def codes(self) -> set[str]:
        return {item.code for item in self.findings}

PROFILES = {"A", "B"}
PRIMITIVES = {"Int", "Bool", "String", "Unit"}
CLOSED_EFFECTS = {"fs.read", "fs.write", "net.send", "clock.read", "process.spawn"}

def _names(value: Any, field: str, unique: bool = True) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(x, str) or not x for x in value):
        raise ModelError(f"{field} must be a list of non-empty strings")
    if unique and len(set(value)) != len(value):
        raise ModelError(f"{field} contains duplicates")
    return tuple(value)

def check_program(program: dict[str, Any], profile: str) -> CheckResult:
    """Check a deliberately small function/call/resource declaration model.

    Profile A: primitive types, closed effect sets, ambient capabilities, and no
    static affine-use check.
    Profile B: positive-int refinement, effect-row annotations, explicit
    capability propagation, and affine resource consumption.
    """
    if profile not in PROFILES:
        raise ModelError("profile must be A or B")
    if not isinstance(program, dict) or set(program) - {"functions", "ambient_capabilities", "resources"}:
        raise ModelError("invalid program envelope")
    functions = program.get("functions")
    if not isinstance(functions, dict) or not functions:
        raise ModelError("functions must be a non-empty object")
    ambient = set(_names(program.get("ambient_capabilities", []), "ambient_capabilities"))
    resources = program.get("resources", {})
    if not isinstance(resources, dict) or any(not isinstance(k, str) or v != "owned" for k, v in resources.items()):
        raise ModelError("resources must map names to 'owned'")

    findings: list[Finding] = []
    direct_effects: dict[str, set[str]] = {}
    direct_caps: dict[str, set[str]] = {}
    calls: dict[str, tuple[str, ...]] = {}
    consumed: dict[str, tuple[str, ...]] = {}

    for name, spec in functions.items():
        if not isinstance(name, str) or not name or not isinstance(spec, dict):
            raise ModelError("invalid function declaration")
        allowed = {"params", "result", "effects", "effect_row", "requires", "calls", "consumes", "positive_params", "known_values"}
        if set(spec) - allowed:
            raise ModelError(f"{name}: unknown declaration fields")
        params = spec.get("params", {})
        if not isinstance(params, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in params.items()):
            raise ModelError(f"{name}: params must map names to type names")
        for ptype in params.values():
            if ptype not in PRIMITIVES and not (profile == "B" and ptype == "PositiveInt"):
                findings.append(Finding("UNKNOWN_TYPE", name, ptype))
        result_type = spec.get("result", "Unit")
        if result_type not in PRIMITIVES and not (profile == "B" and result_type == "PositiveInt"):
            findings.append(Finding("UNKNOWN_TYPE", name, result_type))
        effects = set(_names(spec.get("effects", []), f"{name}.effects"))
        if profile == "A":
            for effect in effects - CLOSED_EFFECTS:
                findings.append(Finding("UNKNOWN_EFFECT", name, effect))
            if spec.get("effect_row") is not None:
                findings.append(Finding("OPEN_EFFECT_ROW_UNSUPPORTED", name, str(spec["effect_row"])))
        elif spec.get("effect_row") is not None and not isinstance(spec["effect_row"], str):
            findings.append(Finding("INVALID_EFFECT_ROW", name, "effect_row must be a string or null"))
        direct_effects[name] = effects
        direct_caps[name] = set(_names(spec.get("requires", []), f"{name}.requires"))
        calls[name] = _names(spec.get("calls", []), f"{name}.calls")
        consumed[name] = _names(spec.get("consumes", []), f"{name}.consumes", unique=False)
        if profile == "B":
            positive = _names(spec.get("positive_params", []), f"{name}.positive_params")
            if set(positive) - set(params):
                findings.append(Finding("UNKNOWN_PARAMETER", name, ",".join(sorted(set(positive) - set(params)))))
            known_values = spec.get("known_values", {})
            if not isinstance(known_values, dict):
                raise ModelError(f"{name}.known_values must be an object")
            for p in positive:
                if params.get(p) not in {"Int", "PositiveInt"}:
                    findings.append(Finding("REFINEMENT_TYPE_MISMATCH", name, p))
                elif p not in known_values:
                    findings.append(Finding("REFINEMENT_UNKNOWN", name, p))
                elif type(known_values[p]) is not int or known_values[p] <= 0:
                    findings.append(Finding("REFINEMENT_DISPROVEN", name, p))
        elif spec.get("positive_params"):
            findings.append(Finding("REFINEMENT_UNSUPPORTED", name, "positive_params"))

    for caller, targets in calls.items():
        for target in targets:
            if target not in functions:
                findings.append(Finding("UNKNOWN_CALLEE", caller, target))

    # Fixed-point summaries support recursive call graphs. They say nothing about
    # execution termination or completeness of a real source-level call graph.
    all_effects = {name: set(effects) for name, effects in direct_effects.items()}
    all_caps = {name: set(caps) for name, caps in direct_caps.items()}
    changed = True
    while changed:
        changed = False
        for name, targets in calls.items():
            for target in targets:
                if target in functions:
                    before = (len(all_effects[name]), len(all_caps[name]))
                    all_effects[name].update(all_effects[target])
                    all_caps[name].update(all_caps[target])
                    changed |= before != (len(all_effects[name]), len(all_caps[name]))

    if profile == "A":
        # Requirements are checked against one ambient program context.
        missing = set().union(*direct_caps.values()) - ambient if direct_caps else set()
        for cap in sorted(missing):
            findings.append(Finding("MISSING_AMBIENT_CAPABILITY", "program", cap))
    else:
        # Transitive capability needs must be declared by each function or supplied
        # by the explicit program context.
        for name, required in all_caps.items():
            missing = required - direct_caps[name] - ambient
            for cap in sorted(missing):
                findings.append(Finding("CAPABILITY_NOT_DECLARED", name, cap))
        # Affine rule: a resource can be consumed at most once in a function.
        for name, uses in consumed.items():
            duplicates = sorted({resource for resource in uses if uses.count(resource) > 1})
            for resource in duplicates:
                findings.append(Finding("RESOURCE_USE_AFTER_MOVE", name, resource))
            for resource in uses:
                if resource not in resources:
                    findings.append(Finding("UNKNOWN_RESOURCE", name, resource))

    status = ("UNKNOWN" if any(item.code == "REFINEMENT_UNKNOWN" for item in findings)
              else "REJECTED" if findings else "ACCEPTED")
    return CheckResult(
        profile, status, tuple(findings),
        tuple((name, tuple(sorted(values))) for name, values in sorted(all_effects.items())),
        tuple((name, tuple(sorted(values))) for name, values in sorted(all_caps.items())),
    )
