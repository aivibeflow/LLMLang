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

def _type_valid(type_expr: Any, profile: str) -> bool:
    """Validate primitive types and Profile B Result<Ok, Err> descriptors."""
    if isinstance(type_expr, str):
        return type_expr in PRIMITIVES or (profile == 'B' and type_expr == 'PositiveInt')
    if profile == "B" and isinstance(type_expr, dict) and set(type_expr) == {"Result"}:
        args = type_expr["Result"]
        return isinstance(args, list) and len(args) == 2 and all(_type_valid(x, profile) for x in args)
    return False

def _type_text(type_expr: Any) -> str:
    if isinstance(type_expr, str):
        return type_expr
    if isinstance(type_expr, dict) and set(type_expr) == {"Result"}:
        args = type_expr["Result"]
        if isinstance(args, list) and len(args) == 2:
            return "Result<" + _type_text(args[0]) + ", " + _type_text(args[1]) + ">"
    return repr(type_expr)

def _names(value: Any, field: str, unique: bool = True) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(x, str) or not x for x in value):
        raise ModelError(f"{field} must be a list of non-empty strings")
    if unique and len(set(value)) != len(value):
        raise ModelError(f"{field} contains duplicates")
    return tuple(value)

def _check_resource_flow(
    function: str,
    flow: Any,
    resources: dict[str, str],
    findings: list[Finding],
) -> None:
    """Check affine consumption over a finite CFG using exact reachable states.

    A state is the set of resources already consumed on one path. Keeping the
    finite set of path states makes joins explicit: paths may join only when
    they agree on each resource's available/consumed state. Cycles converge
    because the state space is bounded by the finite resource set.
    """
    if not isinstance(flow, dict) or set(flow) != {"entry", "blocks"}:
        raise ModelError(f"{function}.resource_flow must contain entry and blocks")
    entry = flow["entry"]
    blocks = flow["blocks"]
    if not isinstance(entry, str) or not entry:
        raise ModelError(f"{function}.resource_flow.entry must be a non-empty string")
    if not isinstance(blocks, dict) or not blocks or entry not in blocks:
        raise ModelError(f"{function}.resource_flow.blocks must contain its entry block")

    normalized: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {}
    for block_name, block in blocks.items():
        if not isinstance(block_name, str) or not block_name or not isinstance(block, dict):
            raise ModelError(f"{function}.resource_flow has an invalid block")
        if set(block) - {"ops", "successors"}:
            raise ModelError(f"{function}.{block_name} has unknown block fields")
        raw_ops = block.get("ops", [])
        raw_successors = block.get("successors", [])
        if not isinstance(raw_ops, list):
            raise ModelError(f"{function}.{block_name}.ops must be a list")
        operations: list[str] = []
        for operation in raw_ops:
            if not isinstance(operation, dict) or set(operation) != {"consume"}:
                raise ModelError(f"{function}.{block_name} operations must be consume records")
            resource = operation["consume"]
            if not isinstance(resource, str) or not resource:
                raise ModelError(f"{function}.{block_name} consume target must be a non-empty string")
            operations.append(resource)
        successors = _names(raw_successors, f"{function}.{block_name}.successors")
        for successor in successors:
            if successor not in blocks:
                raise ModelError(f"{function}.{block_name} references unknown block {successor}")
        normalized[block_name] = (tuple(operations), successors)

    # Each block receives all distinct consumed-resource sets reachable there.
    incoming: dict[str, set[frozenset[str]]] = {name: set() for name in blocks}
    incoming[entry].add(frozenset())
    pending = [entry]
    reported: set[tuple[str, str, str]] = set()

    while pending:
        block_name = pending.pop()
        operations, successors = normalized[block_name]
        outgoing: set[frozenset[str]] = set()
        for state in incoming[block_name]:
            current = set(state)
            for resource in operations:
                if resource not in resources:
                    key = ("UNKNOWN_RESOURCE", block_name, resource)
                    if key not in reported:
                        findings.append(Finding(*key))
                        reported.add(key)
                    continue
                if resource in current:
                    key = ("RESOURCE_USE_AFTER_MOVE", block_name, resource)
                    if key not in reported:
                        findings.append(Finding(*key))
                        reported.add(key)
                else:
                    current.add(resource)
            outgoing.add(frozenset(current))

        if len(incoming[block_name]) > 1:
            all_resources = set().union(*incoming[block_name])
            for resource in sorted(all_resources):
                states = {resource in state for state in incoming[block_name]}
                if len(states) > 1:
                    key = ("RESOURCE_STATE_MISMATCH", block_name, resource)
                    if key not in reported:
                        findings.append(Finding(*key))
                        reported.add(key)

        for successor in successors:
            before = len(incoming[successor])
            incoming[successor].update(outgoing)
            if len(incoming[successor]) != before:
                pending.append(successor)


def _valid_scope(scope: Any) -> bool:
    if not isinstance(scope, str) or not scope.startswith("/") or "\\" in scope:
        return False
    if scope != "/" and (scope.endswith("/") or "//" in scope):
        return False
    return all(part not in {".", ".."} for part in scope.split("/"))


def _scope_contains(parent: str, child: str) -> bool:
    return parent == "/" or child == parent or child.startswith(parent.rstrip("/") + "/")


def _prepare_grants(raw: Any) -> tuple[dict[str, dict[str, Any]], set[str]]:
    if not isinstance(raw, dict):
        raise ModelError("capability_grants must be an object")
    grants: dict[str, dict[str, Any]] = {}
    for gid, item in raw.items():
        if not isinstance(gid, str) or not gid or not isinstance(item, dict):
            raise ModelError("invalid capability grant")
        if set(item) - {"capability", "scope", "parent", "revoked"}:
            raise ModelError(f"{gid}: unknown grant fields")
        cap, scope, parent, revoked = item.get("capability"), item.get("scope"), item.get("parent"), item.get("revoked", False)
        if not isinstance(cap, str) or not cap or not _valid_scope(scope):
            raise ModelError(f"{gid}: invalid capability or scope")
        if parent is not None and (not isinstance(parent, str) or not parent):
            raise ModelError(f"{gid}.parent must be a grant ID or null")
        if type(revoked) is not bool:
            raise ModelError(f"{gid}.revoked must be boolean")
        grants[gid] = {"capability": cap, "scope": scope, "parent": parent, "revoked": revoked}
    for gid, item in grants.items():
        parent_id = item["parent"]
        if parent_id is not None:
            if parent_id not in grants:
                raise ModelError(f"{gid} references unknown parent grant {parent_id}")
            parent = grants[parent_id]
            if item["capability"] != parent["capability"] or not _scope_contains(parent["scope"], item["scope"]):
                raise ModelError(f"{gid} violates parent grant attenuation")
    visiting: set[str] = set()
    visited: set[str] = set()
    def visit(gid: str) -> None:
        if gid in visiting:
            raise ModelError("capability grant parent cycle")
        if gid in visited:
            return
        visiting.add(gid)
        parent_id = grants[gid]["parent"]
        if parent_id is not None:
            visit(parent_id)
        visiting.remove(gid)
        visited.add(gid)
    for gid in grants:
        visit(gid)
    cache: dict[str, bool] = {}
    def revoked(gid: str) -> bool:
        if gid not in cache:
            parent_id = grants[gid]["parent"]
            cache[gid] = grants[gid]["revoked"] or (parent_id is not None and revoked(parent_id))
        return cache[gid]
    return grants, {gid for gid in grants if revoked(gid)}

def check_program(program: dict[str, Any], profile: str) -> CheckResult:
    """Check a deliberately small function/call/resource declaration model.

    Profile A: primitive types, closed effects, ambient capabilities, no affine check.
    Profile B: positive-int refinement, effect rows, transitive capabilities,
    and affine resource consumption (linear lists or branch-sensitive CFGs).
    """
    if profile not in PROFILES:
        raise ModelError("profile must be A or B")
    if not isinstance(program, dict) or set(program) - {"functions", "ambient_capabilities", "resources", "call_graph_complete", "capability_grants"}:
        raise ModelError("invalid program envelope")
    functions = program.get("functions")
    if not isinstance(functions, dict) or not functions:
        raise ModelError("functions must be a non-empty object")
    ambient = set(_names(program.get("ambient_capabilities", []), "ambient_capabilities"))
    resources = program.get("resources", {})
    if not isinstance(resources, dict) or any(not isinstance(k, str) or v != "owned" for k, v in resources.items()):
        raise ModelError("resources must map names to 'owned'")
    call_graph_complete = set(_names(program.get("call_graph_complete", []), "call_graph_complete"))
    if call_graph_complete - set(functions):
        raise ModelError("call_graph_complete references unknown functions")
    grants, revoked_grants = _prepare_grants(program.get("capability_grants", {}))

    findings: list[Finding] = []
    direct_effects: dict[str, set[str]] = {}
    direct_caps: dict[str, set[str]] = {}
    calls: dict[str, tuple[str, ...]] = {}
    consumed: dict[str, tuple[str, ...]] = {}
    resource_flows: dict[str, Any] = {}

    for name, spec in functions.items():
        if not isinstance(name, str) or not name or not isinstance(spec, dict):
            raise ModelError("invalid function declaration")
        allowed = {"params", "result", "effects", "effect_bound", "effect_row", "requires", "calls", "consumes", "resource_flow", "positive_params", "known_values", "call_sites", "grants", "capability_requirements"}
        if set(spec) - allowed:
            raise ModelError(f"{name}: unknown declaration fields")
        params = spec.get("params", {})
        if not isinstance(params, dict) or any(not isinstance(k, str) or not k for k in params):
            raise ModelError(f"{name}: params must map names to type names")
        for ptype in params.values():
            if not _type_valid(ptype, profile):
                findings.append(Finding("UNKNOWN_TYPE", name, _type_text(ptype)))
        result_type = spec.get("result", "Unit")
        if not _type_valid(result_type, profile):
            findings.append(Finding("UNKNOWN_TYPE", name, _type_text(result_type)))
        raw_call_sites = spec.get("call_sites", [])
        if not isinstance(raw_call_sites, list):
            raise ModelError(f"{name}.call_sites must be a list")
        for index, call_site in enumerate(raw_call_sites):
            if not isinstance(call_site, dict) or set(call_site) - {"target", "args", "expected_result", "grants"}:
                raise ModelError(f"{name}.call_sites[{index}] has invalid fields")
            if not isinstance(call_site.get("target"), str) or not call_site["target"]:
                raise ModelError(f"{name}.call_sites[{index}].target must be a non-empty string")
            if "args" not in call_site or not isinstance(call_site["args"], list):
                raise ModelError(f"{name}.call_sites[{index}].args must be a list")
            if "expected_result" in call_site and not _type_valid(call_site["expected_result"], profile):
                findings.append(Finding("UNKNOWN_TYPE", name, _type_text(call_site["expected_result"])))
            _names(call_site.get("grants", []), f"{name}.call_sites[{index}].grants")
        function_grants = _names(spec.get("grants", []), f"{name}.grants")
        if set(function_grants) - set(grants):
            raise ModelError(f"{name}.grants references unknown grants")
        requirements = spec.get("capability_requirements", [])
        if not isinstance(requirements, list):
            raise ModelError(f"{name}.capability_requirements must be a list")
        for req_index, req in enumerate(requirements):
            if not isinstance(req, dict) or set(req) != {"capability", "scope"}:
                raise ModelError(f"{name}.capability_requirements[{req_index}] is malformed")
            if not isinstance(req["capability"], str) or not req["capability"] or not _valid_scope(req["scope"]):
                raise ModelError(f"{name}.capability_requirements[{req_index}] is invalid")
        if profile == "A" and (function_grants or requirements or any(site.get("grants") for site in raw_call_sites)):
            findings.append(Finding("SCOPED_CAPABILITY_UNSUPPORTED", name, "Profile A has no scoped grant model"))
        effects = set(_names(spec.get("effects", []), f"{name}.effects"))
        if profile == "A":
            for effect in effects - CLOSED_EFFECTS:
                findings.append(Finding("UNKNOWN_EFFECT", name, effect))
            if spec.get("effect_row") is not None:
                findings.append(Finding("OPEN_EFFECT_ROW_UNSUPPORTED", name, str(spec["effect_row"])))
        else:
            if spec.get("effect_row") is not None and not isinstance(spec["effect_row"], str):
                findings.append(Finding("INVALID_EFFECT_ROW", name, "effect_row must be a string or null"))
            if spec.get("effect_row") is None:
                for effect in effects - CLOSED_EFFECTS:
                    findings.append(Finding("UNKNOWN_EFFECT", name, effect))
        direct_effects[name] = effects
        if "effect_bound" in spec:
            _names(spec["effect_bound"], f"{name}.effect_bound")
        direct_caps[name] = set(_names(spec.get("requires", []), f"{name}.requires"))
        calls[name] = _names(spec.get("calls", []), f"{name}.calls")
        consumed[name] = _names(spec.get("consumes", []), f"{name}.consumes", unique=False)
        if "resource_flow" in spec:
            if consumed[name]:
                raise ModelError(f"{name}: use consumes or resource_flow, not both")
            resource_flows[name] = spec["resource_flow"]
        if profile == "B":
            positive = _names(spec.get("positive_params", []), f"{name}.positive_params")
            if set(positive) - set(params):
                findings.append(Finding("UNKNOWN_PARAMETER", name, ",".join(sorted(set(positive) - set(params)))))
            known_values = spec.get("known_values", {})
            if not isinstance(known_values, dict):
                raise ModelError(f"{name}.known_values must be an object")
            for p in positive:
                if params.get(p) != "Int" and params.get(p) != "PositiveInt":
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

    for caller, spec in functions.items():
        for index, site in enumerate(spec.get("call_sites", [])):
            target = site["target"]
            subject = f"{caller}#{index}->{target}"
            if target not in calls[caller]:
                raise ModelError(f"{subject}: typed call site is absent from calls")
            if target not in functions:
                continue
            callee = functions[target]
            if "params" not in callee or "result" not in callee:
                findings.append(Finding("CALL_SIGNATURE_UNKNOWN", subject,
                                        "callee must declare params and result for typed checking"))
                continue
            callee_params = callee["params"]
            actual_args = site["args"]
            if len(actual_args) != len(callee_params):
                findings.append(Finding("CALL_ARITY_MISMATCH", subject,
                                        f"expected {len(callee_params)} arguments, got {len(actual_args)}"))
                continue
            for (parameter, parameter_type), actual_type in zip(callee_params.items(), actual_args):
                if not _type_valid(actual_type, profile):
                    findings.append(Finding("UNKNOWN_TYPE", subject, _type_text(actual_type)))
                elif _type_valid(parameter_type, profile) and actual_type != parameter_type:
                    findings.append(Finding("CALL_ARGUMENT_TYPE_MISMATCH", subject,
                                            f"{parameter}: expected {_type_text(parameter_type)}, got {_type_text(actual_type)}"))
            if "expected_result" in site:
                expected = site["expected_result"]
                actual_result = callee["result"]
                if _type_valid(expected, profile) and _type_valid(actual_result, profile) and expected != actual_result:
                    findings.append(Finding("CALL_RESULT_TYPE_MISMATCH", subject,
                                            f"expected {_type_text(expected)}, callee returns {_type_text(actual_result)}"))


    if profile == "B":
        for name, spec in functions.items():
            held = set(spec.get("grants", []))
            for gid in held & revoked_grants:
                findings.append(Finding("CAPABILITY_REVOKED", name, gid))
            for req in spec.get("capability_requirements", []):
                usable = [grants[gid] for gid in held if gid not in revoked_grants and grants[gid]["capability"] == req["capability"]]
                if not any(_scope_contains(g["scope"], req["scope"]) for g in usable):
                    findings.append(Finding("CAPABILITY_SCOPE_NOT_GRANTED", name, req["capability"] + ":" + req["scope"]))

        for caller, spec in functions.items():
            by_target: dict[str, list[dict[str, Any]]] = {}
            for site in spec.get("call_sites", []):
                by_target.setdefault(site["target"], []).append(site)
            held = set(spec.get("grants", []))
            for target in calls[caller]:
                if target not in functions:
                    continue
                requirements = functions[target].get("capability_requirements", [])
                if not requirements:
                    continue
                sites = by_target.get(target, [])
                if not sites:
                    findings.append(Finding("CAPABILITY_DELEGATION_UNKNOWN", caller, f"no explicit grant transfer to {target}"))
                    continue
                for index, site in enumerate(sites):
                    subject = f"{caller}#{index}->{target}"
                    passed = set(site.get("grants", []))
                    if passed - held:
                        raise ModelError(f"{subject} passes grants not held by caller")
                    for gid in passed & revoked_grants:
                        findings.append(Finding("CAPABILITY_REVOKED", subject, gid))
                    for req in requirements:
                        usable = [grants[gid] for gid in passed if gid not in revoked_grants and grants[gid]["capability"] == req["capability"]]
                        if not any(_scope_contains(g["scope"], req["scope"]) for g in usable):
                            findings.append(Finding("CAPABILITY_DELEGATION_INSUFFICIENT", subject, req["capability"] + ":" + req["scope"]))

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

    # An effect bound is meaningful only when the call graph for the full
    # reachable closure is explicitly declared complete. A missing edge cannot
    # be inferred from an empty adjacency list, so absence of completeness
    # evidence yields UNKNOWN rather than a successful empty summary.
    for root, spec in functions.items():
        if "effect_bound" not in spec:
            continue
        reachable: set[str] = set()
        stack = [root]
        unknown_targets: set[str] = set()
        while stack:
            current = stack.pop()
            if current in reachable:
                continue
            reachable.add(current)
            for target in calls[current]:
                if target not in functions:
                    unknown_targets.add(target)
                else:
                    stack.append(target)
        bound = set(spec["effect_bound"])
        excess = all_effects[root] - bound
        for effect in sorted(excess):
            findings.append(Finding("EFFECT_BOUND_EXCEEDED", root, effect))
        incomplete = sorted(reachable - call_graph_complete)
        if incomplete or unknown_targets:
            details = []
            if incomplete:
                details.append("call graph not certified complete for: " + ", ".join(incomplete))
            if unknown_targets:
                details.append("unresolved callees: " + ", ".join(sorted(unknown_targets)))
            findings.append(Finding("EFFECT_SUMMARY_UNKNOWN", root, "; ".join(details)))

    if profile == "A":
        missing = set().union(*direct_caps.values()) - ambient if direct_caps else set()
        for cap in sorted(missing):
            findings.append(Finding("MISSING_AMBIENT_CAPABILITY", "program", cap))
    else:
        for name, required in all_caps.items():
            missing = required - direct_caps[name] - ambient
            for cap in sorted(missing):
                findings.append(Finding("CAPABILITY_NOT_DECLARED", name, cap))
        for name, uses in consumed.items():
            duplicates = sorted({resource for resource in uses if uses.count(resource) > 1})
            for resource in duplicates:
                findings.append(Finding("RESOURCE_USE_AFTER_MOVE", name, resource))
            for resource in uses:
                if resource not in resources:
                    findings.append(Finding("UNKNOWN_RESOURCE", name, resource))
        for name, flow in resource_flows.items():
            _check_resource_flow(name, flow, resources, findings)

    uncertain_codes = {"REFINEMENT_UNKNOWN", "EFFECT_SUMMARY_UNKNOWN", "UNKNOWN_CALLEE", "CALL_SIGNATURE_UNKNOWN", "CAPABILITY_DELEGATION_UNKNOWN"}
    status = ("REJECTED" if any(item.code not in uncertain_codes for item in findings)
              else "UNKNOWN" if findings else "ACCEPTED")
    return CheckResult(
        profile, status, tuple(findings),
        tuple((name, tuple(sorted(values))) for name, values in sorted(all_effects.items())),
        tuple((name, tuple(sorted(values))) for name, values in sorted(all_caps.items())),
    )
