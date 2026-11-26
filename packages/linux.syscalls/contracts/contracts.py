"""Typed syscall contracts and conservative contract-to-contract refinement."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re


CONTRACTS_PATH = Path(__file__).with_name("syscalls.json")
COMMANDS_PATH = Path(__file__).with_name("commands.json")
SCHEMA = "llmlang-linux-syscall-contracts/v1"
COMMAND_SCHEMA = "llmlang-linux-syscall-command-coverage/v1"
PROFILE = "linux-x86_64-native-v1"
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*", re.ASCII)
CLAUSE = re.compile(r"[a-z][a-z0-9-]*", re.ASCII)
SYSFS_SELECTOR = re.compile(r"/sys(?:/[A-Za-z0-9_][A-Za-z0-9_.-]*)+", re.ASCII)


class ContractError(ValueError):
    """Contract data does not conform to the supported syscall profile."""


def canonical_digest(domain, value):
    """Versioned, domain-separated identity over logical data."""
    data = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return f"sha256:{sha256(domain.encode('ascii') + bytes(1) + data.encode('utf-8')).hexdigest()}"


def _fields(value, fields, context):
    if type(value) is not dict or value.keys() != set(fields):
        raise ContractError(f"{context}: expected exactly {', '.join(fields)}")


def _array(value, context):
    if type(value) is not list:
        raise ContractError(f"{context}: expected an array")
    return value


def _unique(items, context):
    if len(items) != len(set(items)):
        raise ContractError(f"{context}: duplicate entries")


def _token(value, pattern, context):
    if type(value) is not str or not pattern.fullmatch(value):
        raise ContractError(f"{context}: invalid token {value!r}")
    return value


def _text(value, context):
    if type(value) is not str or not value or value.strip() != value:
        raise ContractError(f"{context}: expected nonempty text")
    return value


def _strict_object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ContractError("duplicate JSON object field")
    return result


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_strict_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read {path}: {exc}") from exc


def _typed_fields(fields, types, context):
    for field in _array(fields, context):
        _fields(field, ("name", "type"), context)
        _token(field["name"], IDENTIFIER, context)
        _token(field["type"], IDENTIFIER, context)
        if field["type"] not in types:
            raise ContractError(f"{context}: undeclared type {field['type']!r}")
    _unique([field["name"] for field in fields], context)


def _clauses(value, context):
    clauses = {}
    for item in _array(value, context):
        _fields(item, ("id", "statement"), context)
        name = _token(item["id"], CLAUSE, context)
        if name in clauses:
            raise ContractError(f"{context}: duplicate clause {name}")
        clauses[name] = _text(item["statement"], context)
    return dict(sorted(clauses.items()))


def _type_definitions(types):
    if type(types) is not dict or not types:
        raise ContractError("types: expected nonempty object")
    for name, definition in types.items():
        _token(name, IDENTIFIER, "type name")
        if type(definition) is not dict:
            raise ContractError(f"{name}: expected type definition")
        match definition.get("kind"):
            case "scalar" | "opaque" | "resource":
                _fields(definition, ("kind", "description", "invariants"), name)
            case "buffer":
                keys = ("kind", "description", "invariants")
                _fields(definition, keys + (("element",) if "element" in definition else ()), name)
                if "element" in definition:
                    element = _token(definition["element"], IDENTIFIER, name)
                    if element not in types:
                        raise ContractError(f"{name}: undeclared element type {element!r}")
            case "structure":
                _fields(definition, ("kind", "description", "fields", "invariants"), name)
                _typed_fields(definition["fields"], types, name)
                if not definition["fields"]:
                    raise ContractError(f"{name}: empty structure")
            case "array" | "sequence":
                fixed_length = definition["kind"] == "array"
                keys = ("kind", "description", "element", "invariants")
                _fields(definition, keys + (("length",) if fixed_length else ()), name)
                element = _token(definition["element"], IDENTIFIER, name)
                if element not in types:
                    raise ContractError(f"{name}: undeclared element type {element!r}")
                if fixed_length and (type(definition["length"]) is not int or definition["length"] <= 0):
                    raise ContractError(f"{name}: invalid fixed array length")
            case "variant":
                _fields(definition, ("kind", "description", "variants", "invariants"), name)
                names = []
                for variant in _array(definition["variants"], name):
                    _fields(variant, ("name", "fields"), name)
                    names.append(_token(variant["name"], IDENTIFIER, name))
                    _typed_fields(variant["fields"], types, name)
                if not names:
                    raise ContractError(f"{name}: empty variant")
                _unique(names, name)
            case _:
                raise ContractError(f"{name}: unsupported type kind")
        _text(definition["description"], name)
        invariants = _clauses(definition["invariants"], name)
        if definition["kind"] in {"structure", "resource"} and not invariants:
            raise ContractError(f"{name}: managed structures and resources require invariants")
    return types


def _signature(value, types, context):
    _fields(value, ("parameters", "result"), context)
    _typed_fields(value["parameters"], types, context)
    result = _token(value["result"], IDENTIFIER, context)
    if result not in types or types[result]["kind"] != "variant":
        raise ContractError(f"{context}: expected a declared result variant type")
    return value


def _signature_type_definitions(signature, types):
    dependencies = [signature["result"], *(p["type"] for p in signature["parameters"])]
    selected = {}
    while dependencies:
        name = dependencies.pop()
        if name in selected:
            continue
        definition = types[name]
        selected[name] = definition
        if "element" in definition:
            dependencies.append(definition["element"])
        dependencies.extend(field["type"] for field in definition.get("fields", ()))
        for variant in definition.get("variants", ()):
            dependencies.extend(field["type"] for field in variant["fields"])
    return dict(sorted(selected.items()))


@dataclass(frozen=True)
class Contract:
    id: str
    operation: str
    role: str
    profile: str
    signature: dict
    types: dict
    preconditions: dict[str, str]
    guarantees: dict[str, str]
    effects: dict[str, str]
    assumptions: dict[str, str]


@dataclass(frozen=True)
class Operation:
    name: str
    revision: int
    interface_revision: str
    public: Contract
    provided: Contract
    profile: str
    assumptions: dict[str, str]
    sources: tuple[str, ...]


def _contract(operation, role, signature, types, clauses):
    _fields(clauses, ("preconditions", "guarantees", "effects", "assumptions"), f"{operation}.{role}")
    normalized = {
        group: _clauses(items, f"{operation}.{role}.{group}") for group, items in clauses.items()
    }
    if not normalized["guarantees"] or not normalized["effects"]:
        raise ContractError(f"{operation}.{role}: guarantees and effects are required")
    record = dict(operation=operation, role=role, profile=PROFILE, signature=signature, types=types, **normalized)
    return Contract(canonical_digest(f"{SCHEMA}/{role}", record), **record)


def load_contracts(path=CONTRACTS_PATH) -> dict[str, Operation]:
    """Read and validate a contract set without asserting any provider-body claim."""
    document = _read_json(path)
    _fields(document, ("schema", "profile", "types", "operations"), "contract set")
    if document["schema"] != SCHEMA or document["profile"] != PROFILE:
        raise ContractError("unsupported syscall contract schema or profile")
    types = _type_definitions(document["types"])
    operations = {}
    for item in _array(document["operations"], "operations"):
        _fields(item, ("name", "revision", "signature", "public", "provided", "sources"), "operation")
        name = _token(item["name"], IDENTIFIER, "operation name")
        revision = item["revision"]
        if name in operations or type(revision) is not int or not 0 < revision < 2**63:
            raise ContractError(f"{name}: duplicate operation or invalid revision")
        signature = _signature(item["signature"], types, name)
        selected_types = _signature_type_definitions(signature, types)
        public = _contract(name, "public", signature, selected_types, item["public"])
        provided = _contract(name, "provided", signature, selected_types, item["provided"])
        interface_revision = canonical_digest(f"{SCHEMA}/interface", {
            "name": f"linux.syscalls.{name}", "revision": revision, "public_contract": public.id,
        })
        sources = tuple(_text(source, name) for source in _array(item["sources"], name))
        if not sources:
            raise ContractError(f"{name}: missing UAPI and semantic sources")
        operations[name] = Operation(name, revision, interface_revision, public, provided, PROFILE, public.assumptions, sources)
    if not operations:
        raise ContractError("empty syscall contract set")
    return operations


def load_commands(operations, path=COMMANDS_PATH) -> dict:
    """Check explicit supported-command coverage and links to typed contracts."""
    document = _read_json(path)
    _fields(document, ("schema", "profile", "kernel", "families"), "command set")
    if document["schema"] != COMMAND_SCHEMA or document["profile"] != PROFILE:
        raise ContractError("unsupported syscall command schema or profile")
    kernel = document["kernel"]
    _fields(kernel, ("tag", "commit"), "kernel")
    _token(kernel["tag"], re.compile(r"v[0-9]+\.[0-9]+(?:\.[0-9]+)?"), "kernel tag")
    _token(kernel["commit"], re.compile(r"[0-9a-f]{40}"), "kernel commit")
    families = document["families"]
    if type(families) is not dict or not families:
        raise ContractError("expected a nonempty command family set")
    operation_families = {}
    prefix = f"https://github.com/torvalds/linux/blob/{kernel['commit']}/"
    for name, family in families.items():
        _token(name, IDENTIFIER, "syscall name")
        _fields(family, ("unlisted", "commands", "limit"), name)
        if family["unlisted"] != "unsupported":
            raise ContractError(f"{name}: commands absent from this inventory must be unsupported")
        _text(family["limit"], name)
        command_names, command_selectors = [], []
        for command in _array(family["commands"], name):
            fields = ("name", "value", "operation", "uapi", "scope")
            if type(command) is dict and "runtime_selector" in command:
                fields += ("runtime_selector",)
            _fields(command, fields, name)
            command_names.append(_token(command["name"], IDENTIFIER, name))
            value = command["value"]
            if type(value) is not int or not 0 <= value <= 0xffff_ffff:
                raise ContractError(f"{name}: invalid command value")
            runtime_selector = None
            if "runtime_selector" in command:
                runtime_selector = _token(command["runtime_selector"], SYSFS_SELECTOR, f"{name} runtime selector")
            command_selectors.append((runtime_selector, value))
            operation = _token(command["operation"], IDENTIFIER, name)
            if operation not in operations:
                raise ContractError(f"{name}: missing qualified operation for {operation}")
            if operation_families.setdefault(operation, name) != name:
                raise ContractError(f"{name}: command operation {operation} also belongs to another native family")
            if not _text(command["uapi"], name).startswith(prefix):
                raise ContractError(f"{name}: expected an immutable reference to the kernel UAPI")
            _text(command["scope"], name)
        _unique(command_names, f"{name} command names")
        _unique(command_selectors, f"{name} command selectors")
    return document


def refinement(public: Contract, provided: Contract) -> list[str]:
    """Check structural inclusion of exact opaque clauses, with no implication inference."""
    failures = []
    if (public.role, provided.role) != ("public", "provided"):
        failures.append("unexpected contract roles")
    if (public.operation, public.profile, public.signature, public.types) != (
        provided.operation, provided.profile, provided.signature, provided.types,
    ):
        failures.append("incompatible operation, execution profile or typed signature")
    for context, required, allowed in (
        ("added provider preconditions", provided.preconditions, public.preconditions),
        ("added provider assumptions", provided.assumptions, public.assumptions),
        ("missing public guarantees", public.guarantees, provided.guarantees),
        ("additional provider effects", provided.effects, public.effects),
    ):
        mismatches = sorted(name for name, value in required.items() if allowed.get(name) != value)
        if mismatches:
            failures.append(f"{context}: {', '.join(mismatches)}")
    return failures


def render(operation: Operation) -> dict:
    """Expose both contracts and all applicable premises for human review."""
    failures = refinement(operation.public, operation.provided)
    return {
        "qualified_name": f"linux.syscalls.{operation.name}",
        "interface_revision": operation.interface_revision,
        "revision": operation.revision,
        "profile": operation.profile,
        "signature": operation.public.signature,
        "types": operation.public.types,
        "sources": list(operation.sources),
        "contracts": {
            contract.role: {
                "id": contract.id,
                "preconditions": contract.preconditions,
                "guarantees": contract.guarantees,
                "effects": contract.effects,
                "assumptions": contract.assumptions,
            }
            for contract in (operation.public, operation.provided)
        },
        "refinement": {
            "method": "exact clause inclusion",
            "status": "REJECTED" if failures else "CONDITIONAL" if operation.assumptions else "ESTABLISHED",
            "failures": failures,
        },
        "provider_conformance": {"status": "UNSUPPORTED", "scope": "Full syscall contract semantics"},
    }
