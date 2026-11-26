"""Typed contracts over bounded, supplied execution observations."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

from .frontend import MAX_I64, MIN_I64


CONTRACT = "llmlang-trace-contract/v1"
TRACE = "llmlang-observation-trace/v1"
EVIDENCE = "llmlang-trace-evidence/v1"
HEADER = "Controlled trace Contract IR version 1."
IDENTIFIER = r"[A-Za-z_][A-Za-z_0-9]*"
DIGEST = r"sha256:[0-9a-f]{64}"
TYPES = ("Bool", "I64", "Symbol", "Hash")
OUTCOMES = ("success", "error", "cancelled", "partial")


class ProfileError(ValueError):
    """Malformed, ill-typed, or unsupported profile data."""


def object_fields(value, keys, context):
    if type(value) is not dict or value.keys() != set(keys):
        raise ProfileError(f"{context}: expected fields {', '.join(keys)}")
    return value


def array(value, context):
    if type(value) is not list:
        raise ProfileError(f"{context}: expected a list")
    return value


def patterned(value, pattern, context):
    if type(value) is not str or re.fullmatch(pattern, value) is None:
        raise ProfileError(f"{context}: invalid value {value!r}")
    return value


def name(value):
    return patterned(value, IDENTIFIER, "identifier")


def digest(value):
    return patterned(value, DIGEST, "SHA-256 identity")


def natural(value):
    if type(value) is not int or not 0 <= value <= MAX_I64:
        raise ProfileError("expected a nonnegative I64")
    return value


def closed_set(value, acceptable, context):
    items = [name(item) for item in array(value, context)]
    if len(items) != len(set(items)) or not set(items) <= set(acceptable):
        raise ProfileError(f"{context}: unknown or duplicate entries")
    return sorted(items)


def vocabulary(raw, context):
    if type(raw) is not dict:
        raise ProfileError(f"{context}: expected a typed vocabulary")
    for key, typ in raw.items():
        name(key)
        if typ not in TYPES:
            raise ProfileError(f"{context}.{key}: unsupported type {typ!r}")
    return dict(sorted(raw.items()))


def declared(key, vocabulary, typ=None):
    name(key)
    if key not in vocabulary or (typ is not None and vocabulary[key] != typ):
        suffix = f" of type {typ}" if typ else ""
        raise ProfileError(f"{key}: expected declared name{suffix}")
    return key


def typed_value(value, typ):
    match typ:
        case "Bool" if type(value) is bool:
            return value
        case "I64" if type(value) is int and MIN_I64 <= value <= MAX_I64:
            return value
        case "Symbol":
            return name(value)
        case "Hash":
            return digest(value)
    raise ProfileError(f"expected {typ}, got {value!r}")


# Parser expressions are independent of the prose emitted by the renderer.
LIST = r"\[([^\[\]]*)\]"
ID = f"({IDENTIFIER})"
HASH = f"({DIGEST})"
NAT = r"(0|[1-9][0-9]*)"
GRAMMAR = {
    "invariant": (("field",), rf"Field {ID} is nonnegative before and after the execution\."),
    "frame": (("fields",), rf"Only state fields in {LIST} may change\."),
    "effects": (("events",), rf"Only events in {LIST} may occur\."),
    "ownership": (
        ("acquire", "release", "field"),
        rf"Each {ID} acquires and each {ID} releases the resource in field {ID}\. "
        r"Each acquired resource must be acquired and released exactly once by completion\.",
    ),
    "atomicity": (
        ("outcomes", "fields", "events"),
        rf"For outcomes {LIST}, preserve state fields {LIST} and allow only events {LIST}\.",
    ),
    "decreases": (
        ("event", "field"),
        rf"At each {ID}, the nonnegative rank in field {ID} strictly decreases after its first observation\.",
    ),
    "protocol": (
        ("initial", "terminal", "transitions"),
        rf"Protocol starts in {ID} and ends in one of {LIST} with transitions {LIST}\.",
    ),
    "deadline": (
        ("trigger", "response", "ticks"),
        rf"Each {ID} must be followed by {ID} within {NAT} ticks, inclusive\.",
    ),
    "authority": (("event", "field", "allowed"), rf"For {ID}, the principal in field {ID} must be one of {LIST}\."),
    "budget": (("maximum", "event"), rf"At most {NAT} occurrences of {ID} are allowed\."),
    "comparison": (
        ("reference_subject", "inputs", "outputs"),
        rf"Compared with implementation {HASH}, executions agreeing on input fields {LIST} "
        rf"must agree on output fields {LIST}, outcome and all ordered events with their ticks\.",
    ),
    "binding": (
        ("event", "implementation", "required", "public", "provided"),
        rf"Every {ID} must select implementation {HASH} with required Contract {HASH}, "
        rf"public Contract {HASH} and provided Contract {HASH}\.",
    ),
    "assumption": (("premise",), rf"Assume external premise {HASH} with open evidence\."),
}


def normalize_clause(clause, state, events):
    if type(clause) is not dict or type(clause.get("kind")) is not str or clause["kind"] not in GRAMMAR:
        kind = clause.get("kind") if isinstance(clause, dict) else clause
        raise ProfileError(f"unsupported trace clause {kind!r}")
    kind = clause["kind"]
    object_fields(clause, ("id", "kind", *GRAMMAR[kind][0]), kind)
    result = dict(clause, id=name(clause["id"]))
    match kind:
        case "invariant":
            declared(result["field"], state, "I64")
        case "frame" | "atomicity":
            result["fields"] = closed_set(clause["fields"], state, kind)
            if kind == "atomicity":
                result["outcomes"] = closed_set(clause["outcomes"], OUTCOMES[1:], kind)
                result["events"] = closed_set(clause["events"], events, kind)
                if not result["outcomes"]:
                    raise ProfileError("atomicity requires at least one nonsuccess outcome")
        case "effects":
            result["events"] = closed_set(clause["events"], events, kind)
        case "ownership":
            for role in ("acquire", "release"):
                declared(result["field"], events[declared(result[role], events)], "Symbol")
            if result["acquire"] == result["release"]:
                raise ProfileError("ownership acquire and release events must differ")
        case "decreases" | "authority":
            event = events[declared(result["event"], events)]
            declared(result["field"], event, "Symbol" if kind == "authority" else "I64")
            if kind == "authority":
                allowed = array(clause["allowed"], kind)
                result["allowed"] = closed_set(allowed, allowed, kind)
        case "protocol":
            initial = name(result["initial"])
            transitions = []
            keys = set()
            states = {initial}
            for transition in array(clause["transitions"], kind):
                if len(array(transition, "protocol transition")) != 3:
                    raise ProfileError("protocol transition must name current state, event, and next state")
                current, event, following = transition
                serial = [name(current), declared(event, events), name(following)]
                if tuple(serial[:2]) in keys:
                    raise ProfileError("nondeterministic protocol transition")
                keys.add(tuple(serial[:2]))
                states.update((current, following))
                transitions.append(serial)
            result["transitions"] = sorted(transitions)
            result["terminal"] = closed_set(clause["terminal"], states, kind)
            if not result["terminal"]:
                raise ProfileError("protocol requires a terminal state")
        case "deadline":
            declared(result["trigger"], events)
            declared(result["response"], events)
            natural(result["ticks"])
            if result["trigger"] == result["response"]:
                raise ProfileError("deadline trigger and response events must differ")
        case "budget":
            declared(result["event"], events)
            natural(result["maximum"])
        case "comparison":
            digest(result["reference_subject"])
            for role in ("inputs", "outputs"):
                result[role] = closed_set(clause[role], state, kind)
        case "binding":
            event = events[declared(result["event"], events)]
            for role in ("implementation", "required", "public", "provided"):
                declared(role, event, "Hash")
                digest(result[role])
        case "assumption":
            digest(result["premise"])
    return result


def normalize_contract(raw):
    object_fields(raw, ("schema", "state", "events", "clauses"), "trace Contract")
    if raw["schema"] != CONTRACT:
        raise ProfileError(f"unsupported Contract schema {raw['schema']!r}")
    state = vocabulary(raw["state"], "state")
    if type(raw["events"]) is not dict:
        raise ProfileError("expected an event vocabulary")
    events = {name(event): vocabulary(fields, event) for event, fields in raw["events"].items()}
    clauses = [normalize_clause(clause, state, events) for clause in array(raw["clauses"], "clauses")]
    if not clauses or len({clause["id"] for clause in clauses}) != len(clauses):
        raise ProfileError("expected at least one clause and distinct clause identifiers")
    return {
        "schema": CONTRACT, "state": state, "events": dict(sorted(events.items())),
        "clauses": sorted(clauses, key=lambda clause: clause["id"]),
    }


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def identity(context, value):
    return "sha256:" + sha256(context.encode("ascii") + b"\0" + canonical(value)).hexdigest()


def enumerated(items):
    return "[" + ", ".join(items) + "]"


def describe(clause):
    match clause:
        case {"kind": "invariant", "field": field}:
            return f"Field {field} is nonnegative before and after the execution."
        case {"kind": "frame", "fields": fields}:
            return f"Only state fields in {enumerated(fields)} may change."
        case {"kind": "effects", "events": events}:
            return f"Only events in {enumerated(events)} may occur."
        case {"kind": "ownership", "acquire": acquire, "release": release, "field": field}:
            return (f"Each {acquire} acquires and each {release} releases the resource in field {field}. "
                    "Each acquired resource must be acquired and released exactly once by completion.")
        case {"kind": "atomicity", "outcomes": outcomes, "fields": fields, "events": events}:
            return (f"For outcomes {enumerated(outcomes)}, preserve state fields {enumerated(fields)} "
                    f"and allow only events {enumerated(events)}.")
        case {"kind": "decreases", "event": event, "field": field}:
            return (f"At each {event}, the nonnegative rank in field {field} strictly decreases "
                    "after its first observation.")
        case {"kind": "protocol", "initial": initial, "terminal": terminal, "transitions": transitions}:
            edges = [f"{current} + {event} -> {following}" for current, event, following in transitions]
            return f"Protocol starts in {initial} and ends in one of {enumerated(terminal)} with transitions {enumerated(edges)}."
        case {"kind": "deadline", "trigger": trigger, "response": response, "ticks": ticks}:
            return f"Each {trigger} must be followed by {response} within {ticks} ticks, inclusive."
        case {"kind": "authority", "event": event, "field": field, "allowed": allowed}:
            return f"For {event}, the principal in field {field} must be one of {enumerated(allowed)}."
        case {"kind": "budget", "event": event, "maximum": maximum}:
            return f"At most {maximum} occurrences of {event} are allowed."
        case {"kind": "comparison", "reference_subject": subject, "inputs": inputs, "outputs": outputs}:
            return (f"Compared with implementation {subject}, executions agreeing on input fields {enumerated(inputs)} "
                    f"must agree on output fields {enumerated(outputs)}, outcome and all ordered events with their ticks.")
        case {"kind": "binding", "event": event, "implementation": implementation,
              "required": required, "public": public, "provided": provided}:
            return (f"Every {event} must select implementation {implementation} with required Contract {required}, "
                    f"public Contract {public} and provided Contract {provided}.")
        case {"kind": "assumption", "premise": premise}:
            return f"Assume external premise {premise} with open evidence."
    raise ProfileError(f"unsupported trace clause {clause!r}")


def render_contract(contract):
    contract = normalize_contract(contract)
    lines = [HEADER]
    lines.extend(f"State field {field} has type {typ}." for field, typ in contract["state"].items())
    for event, fields in contract["events"].items():
        typed_fields = enumerated(f"{field} as {typ}" for field, typ in fields.items())
        lines.append(f"Event {event} carries {typed_fields}.")
    lines.extend(f"Clause {clause['id']}. {describe(clause)}" for clause in contract["clauses"])
    return "\n".join(lines) + "\n"


def split_items(raw):
    return raw.split(", ") if raw else []


def parse_clause(clause_id, sentence):
    for kind, (fields, pattern) in GRAMMAR.items():
        parsed = re.fullmatch(pattern, sentence)
        if parsed is None:
            continue
        result = {"id": clause_id, "kind": kind}
        for field, value in zip(fields, parsed.groups(), strict=True):
            if field in {"fields", "events", "outcomes", "terminal", "allowed", "inputs", "outputs"}:
                result[field] = split_items(value)
            elif field == "transitions":
                edges = []
                for edge in split_items(value):
                    parsed_edge = re.fullmatch(rf"{ID} \+ {ID} -> {ID}", edge)
                    if parsed_edge is None:
                        raise ProfileError(f"invalid controlled protocol transition {edge!r}")
                    edges.append(list(parsed_edge.groups()))
                result[field] = edges
            elif field in {"maximum", "ticks"}:
                result[field] = int(value)
            else:
                result[field] = value
        return result
    raise ProfileError(f"unsupported controlled trace clause {clause_id}")


def parse_controlled(text):
    lines = text.splitlines()
    if not lines or lines[0] != HEADER:
        raise ProfileError("unsupported controlled trace presentation version")
    state, events, clauses = {}, {}, []
    for line in lines[1:]:
        if field := re.fullmatch(rf"State field {ID} has type {ID}\.", line):
            if field[1] in state:
                raise ProfileError("duplicate controlled state field")
            state[field[1]] = field[2]
        elif event := re.fullmatch(rf"Event {ID} carries {LIST}\.", line):
            if event[1] in events:
                raise ProfileError("duplicate controlled event")
            fields = {}
            for descriptor in split_items(event[2]):
                field = re.fullmatch(rf"{ID} as {ID}", descriptor)
                if not field or field[1] in fields:
                    raise ProfileError("invalid or duplicate controlled event field")
                fields[field[1]] = field[2]
            events[event[1]] = fields
        elif clause := re.fullmatch(rf"Clause {ID}\. (.+)", line):
            clauses.append(parse_clause(*clause.groups()))
        else:
            raise ProfileError(f"unexpected controlled trace line {line!r}")
    return normalize_contract({"schema": CONTRACT, "state": state, "events": events, "clauses": clauses})


def checked_render(contract):
    text = render_contract(contract)
    if parse_controlled(text) != normalize_contract(contract):
        raise ProfileError("controlled trace rendering changed the normalized Contract")
    return text


def normalize_trace(raw, contract):
    keys = ("schema", "subject", "pre", "post", "complete", "outcome", "events")
    object_fields(raw, keys, "trace")
    if raw["schema"] != TRACE:
        raise ProfileError(f"unsupported trace schema {raw['schema']!r}")
    digest(raw["subject"])
    for scope in ("pre", "post"):
        state = contract["state"]
        object_fields(raw[scope], state, scope)
        for field, typ in state.items():
            typed_value(raw[scope][field], typ)
    complete, outcome = raw["complete"], raw["outcome"]
    if type(complete) is not bool or (complete and outcome not in OUTCOMES) or (not complete and outcome is not None):
        raise ProfileError("complete observations require an outcome and prefixes have no outcome")
    tick = 0
    for event in array(raw["events"], "trace events"):
        object_fields(event, ("name", "tick", "fields"), "trace event")
        fields = contract["events"][declared(event["name"], contract["events"])]
        if natural(event["tick"]) < tick:
            raise ProfileError("event ticks must be nondecreasing")
        tick = event["tick"]
        object_fields(event["fields"], fields, event["name"])
        for field, typ in fields.items():
            typed_value(event["fields"][field], typ)
    return raw


def observed(clause, trace, reference):
    """Evaluate one clause on an observation, or return None for missing evidence."""
    pre, post, events = trace["pre"], trace["post"], trace["events"]
    complete = trace["complete"]
    match clause:
        case {"kind": "invariant", "field": field}:
            if pre[field] < 0:
                return False
            return post[field] >= 0 if complete else None
        case {"kind": "frame", "fields": fields}:
            return all(pre[field] == post[field] for field in pre.keys() - set(fields)) if complete else None
        case {"kind": "effects", "events": allowed}:
            return all(event["name"] in allowed for event in events)
        case {"kind": "ownership", "acquire": acquire, "release": release, "field": field}:
            live = set()
            used = set()
            for event in events:
                if event["name"] == acquire:
                    resource = event["fields"][field]
                    if resource in used:
                        return False
                    used.add(resource)
                    live.add(resource)
                elif event["name"] == release:
                    resource = event["fields"][field]
                    if resource not in live:
                        return False
                    live.remove(resource)
            return not live if complete else None
        case {"kind": "atomicity", "outcomes": outcomes, "fields": fields, "events": allowed}:
            if not complete:
                return None
            return trace["outcome"] not in outcomes or (
                all(pre[field] == post[field] for field in fields)
                and all(event["name"] in allowed for event in events)
            )
        case {"kind": "decreases", "event": name, "field": field}:
            ranks = [event["fields"][field] for event in events if event["name"] == name]
            return all(rank >= 0 for rank in ranks) and all(left > right for left, right in zip(ranks, ranks[1:]))
        case {"kind": "protocol", "initial": state, "terminal": terminal, "transitions": transitions}:
            edges = {(before, event): after for before, event, after in transitions}
            for event in events:
                state = edges.get((state, event["name"]))
                if state is None:
                    return False
            return state in terminal if complete else None
        case {"kind": "deadline", "trigger": trigger, "response": response, "ticks": ticks}:
            oldest = None
            for event in events:
                tick = event["tick"]
                if oldest is not None and tick - oldest > ticks:
                    return False
                if event["name"] == trigger and oldest is None:
                    oldest = tick
                elif event["name"] == response:
                    oldest = None
            return oldest is None if complete else None
        case {"kind": "authority", "event": name, "field": field, "allowed": allowed}:
            return all(event["fields"][field] in allowed for event in events if event["name"] == name)
        case {"kind": "budget", "event": name, "maximum": maximum}:
            return sum(event["name"] == name for event in events) <= maximum
        case {"kind": "comparison", "reference_subject": subject, "inputs": inputs, "outputs": outputs}:
            if (reference is None or not complete or not reference["complete"] or reference["subject"] != subject
                    or any(pre[field] != reference["pre"][field] for field in inputs)):
                return None
            return (trace["outcome"] == reference["outcome"] and events == reference["events"]
                    and all(post[field] == reference["post"][field] for field in outputs))
        case {"kind": "binding", "event": name}:
            return all(event["fields"][role] == clause[role] for event in events if event["name"] == name
                       for role in ("implementation", "required", "public", "provided"))
    return None


def check_trace(contract, trace, *, reference=None):
    """Return evidence bound to this checker and the exact supplied observations."""
    contract = normalize_contract(contract)
    trace = normalize_trace(trace, contract)
    if reference is not None:
        reference = normalize_trace(reference, contract)
    clauses = []
    for clause in contract["clauses"]:
        result = observed(clause, trace, reference)
        if result is False:
            status = "VIOLATED"
        elif clause["kind"] == "assumption":
            status = "CONDITIONAL"
        elif result is None or not trace["complete"]:
            status = "UNKNOWN"
        else:
            status = "CHECKED"
        row = {"id": clause["id"], "kind": clause["kind"], "status": status}
        if status == "CONDITIONAL":
            row["open_premise"] = clause["premise"]
        clauses.append(row)
    statuses = {row["status"] for row in clauses}
    status = next(candidate for candidate in ("VIOLATED", "CONDITIONAL", "UNKNOWN", "CHECKED") if candidate in statuses)
    report = {
        "schema": EVIDENCE, "claim": "supplied observations only", "status": status,
        "checker_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "contract_hash": identity(CONTRACT, contract),
        "trace_hash": identity(TRACE, trace), "subject": trace["subject"],
        "reference_trace_hash": identity(TRACE, reference) if reference is not None else None,
        "clauses": clauses,
    }
    return {**report, "evidence_hash": identity(EVIDENCE, report)}


def strict_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProfileError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def read(path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_pairs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("render").add_argument("contract", type=Path)
    actions.add_parser("parse").add_argument("controlled", type=Path)
    check = actions.add_parser("check")
    check.add_argument("contract", type=Path)
    check.add_argument("trace", type=Path)
    check.add_argument("--reference", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "parse":
            contract = parse_controlled(args.controlled.read_text(encoding="utf-8"))
            print(json.dumps(contract, sort_keys=True, indent=2))
            return 0
        contract = read(args.contract)
        if args.action == "render":
            print(checked_render(contract), end="")
            return 0
        report = check_trace(contract, read(args.trace), reference=read(args.reference) if args.reference else None)
        print(json.dumps(report, sort_keys=True, indent=2))
        return int(report["status"] != "CHECKED")
    except ValueError as exc:
        print(json.dumps({"status": "UNSUPPORTED", "diagnostic": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    except OSError as exc:
        print(json.dumps({"status": "ERROR", "diagnostic": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
