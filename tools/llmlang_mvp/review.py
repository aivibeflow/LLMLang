"""Build a revision-bound review packet and authenticate a reviewer receipt."""

import hashlib
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

from . import contract, contract_wire, runtime


DEFAULT_SCENARIOS = Path(__file__).with_name("calculator.scenarios.json")
CALCULATOR_REQUIREMENTS = Path(__file__).resolve().parents[2] / "examples/0003-calculator.md"
SCENARIO_SCHEMA = "llmlang-scalar-review-scenarios/v1"
RECEIPT_SCHEMA = "llmlang-signed-review/v1"
RECEIPT_DOMAIN = b"LLMLang Ed25519 review approval v1\x00"
# RFC 8410 SubjectPublicKeyInfo with the Ed25519 algorithm and a 32-byte key.
ED25519_SPKI_PREFIX = bytes.fromhex("302a300506032b6570032100")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _unique_members(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError(f"duplicate JSON member {name!r}")
        result[name] = value
    return result


def _parse_json(data):
    return json.loads(data.decode("utf-8"), object_pairs_hook=_unique_members)


def _clauses(definition):
    for index, clause in enumerate(definition.requires):
        yield f"requirement-{index + 1}", f"requires/{index}", clause
    for index, clause in enumerate(definition.ensures):
        yield f"guarantee-{index + 1}", f"ensures/{index}", clause
    for error, clauses in definition.errors.items():
        for index, clause in enumerate(clauses):
            yield f"error-{error}-{index + 1}", f"errors/{error}/{index}", clause


def _clause_text(value):
    if value is None:
        return {}
    result = {}
    for line in contract.checked_render(value).splitlines():
        match = contract.CLAUSE_HEADER.match(line)
        if match:
            result[match[1]] = line[match.end():]
    return result


def _contract_differences(previous, current):
    for name in sorted(previous.keys() | current.keys()):
        for role in ("public", "provided"):
            before = previous.get(name, {}).get(role)
            after = current.get(name, {}).get(role)
            if before == after:
                continue
            old_clauses, new_clauses = _clause_text(before), _clause_text(after)
            clauses = []
            for label in sorted(old_clauses.keys() | new_clauses.keys()):
                old_text, new_text = old_clauses.get(label), new_clauses.get(label)
                if old_text == new_text:
                    continue
                change = "added" if old_text is None else "removed" if new_text is None else "changed"
                clauses.append({"clause": label, "change": change, "before": old_text, "after": new_text})
            yield {
                "function": name,
                "role": role,
                "before": _contract_boundary(before),
                "after": _contract_boundary(after),
                "clause_changes": clauses,
            }


def _contract_boundary(value):
    if value is None:
        return None
    return {
        "identity": contract.contract_hash(value),
        "parameters": value.parameters,
        "result": value.returns,
        "errors": sorted(value.errors),
    }


def _is_typed(value, kind):
    if kind == "bool":
        return type(value) is bool
    return type(value) is int and runtime.MIN_I64 <= value <= runtime.MAX_I64


def _scenario_observations(definition, args, actual):
    names = {name: value for (name, _), value in zip(definition.parameters, args, strict=True)}
    observations = {}
    in_domain = contract.holds(definition.requires, names)
    for label, location, clause in _clauses(definition):
        parts = location.split("/")
        if parts[0] == "requires":
            observations[label] = contract.holds((clause,), names)
        elif in_domain and actual.error is None and parts[0] == "ensures":
            observations[label] = contract.holds((clause,), names | {"result": actual.value})
        elif in_domain and parts[:2] == ["errors", actual.error]:
            observations[label] = contract.holds((clause,), names)
    return {
        "domain_accepts_input": in_domain,
        "outcome_allowed": contract.admits_outcome(definition, names, actual) if in_domain else None,
        "applicable_clauses": observations,
    }


def _scenario_evidence(program, definitions, data):
    document = _parse_json(data)
    if (not isinstance(document, dict) or set(document) != {"schema", "scenarios"}
            or document["schema"] != SCENARIO_SCHEMA):
        raise ValueError(f"expected a {SCENARIO_SCHEMA} scenario document")
    rows = document["scenarios"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("review scenarios must be a nonempty array")
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"id", "function", "arguments", "expected", "requirements"}:
            raise ValueError("invalid review scenario fields")
        identifier, function = row["id"], row["function"]
        args, expected, references = row["arguments"], row["expected"], row["requirements"]
        if not isinstance(identifier, str) or not identifier.strip() or identifier in seen:
            raise ValueError(f"empty or duplicate review scenario identifier {identifier!r}")
        seen.add(identifier)
        if not isinstance(function, str) or function not in definitions or function not in program["functions"]:
            raise ValueError(f"review scenario {identifier!r} names an unknown function")
        signature = program["functions"][function]
        if (not isinstance(args, list) or len(args) != len(signature["params"])
                or not all(_is_typed(value, kind) for value, (_, kind) in zip(args, signature["params"]))):
            raise ValueError(f"review scenario {identifier!r} arguments do not match {function}")
        if not isinstance(references, list) or not all(isinstance(item, str) and item.strip() for item in references):
            raise ValueError(f"review scenario {identifier!r} requirement references must be text")
        if (not isinstance(expected, dict) or not (
            set(expected) == {"value"} and _is_typed(expected["value"], signature["result"])
            or set(expected) == {"error"} and isinstance(expected["error"], str)
            and contract.IDENTIFIER.fullmatch(expected["error"])
        )):
            raise ValueError(f"invalid expected outcome in review scenario {identifier!r}")
        actual = runtime.evaluate(program, function, args)
        outcome = {"value": actual.value} if actual.error is None else {"error": actual.error}
        assessments = {
            role: _scenario_observations(definition, args, actual)
            for role, definition in definitions[function].items()
        }
        passes = expected == outcome and all(
            result["domain_accepts_input"] and result["outcome_allowed"]
            for result in assessments.values()
        )
        yield dict(row, observed=outcome, contract_observations=assessments, passed=passes)


def review_packet(
    program, definitions, inputs, *, contract_input="contracts", contract_pointer_prefix="/contracts",
    scenarios_path=None, previous_contracts_path=None, require_pass=False,
):
    """Render the exact graph, source anchors, contracts and scenario observations."""
    if contract_input not in inputs:
        raise ValueError("review requires the exact Contract IR input identity")
    scenario_data = Path(scenarios_path or DEFAULT_SCENARIOS).read_bytes()
    scenarios = list(_scenario_evidence(program, definitions, scenario_data))
    failures = [item["id"] for item in scenarios if not item["passed"]]
    if require_pass and failures:
        raise ValueError(f"review scenario observations disagree with the expected outcome or Contract: {_json(failures)}")

    lines = [
        "LLMLang scalar review packet v1",
        f"SPG snapshot: {_digest(_json(program).encode('utf-8'))}",
        *(f"Input revision: {_json(path)} {_digest_label(digest)}" for path, digest in sorted(inputs.items())),
        f"Scenario input revision: {_digest(scenario_data)}",
        "Scope: scalar function outcomes under declared input domains.",
        "Assumptions: the validated scalar SPG, checked I64 operations, and the scenario inputs below.",
        "Scenario evidence is finite reference execution. The machine verification gate checks body conformance and refinement separately.",
        "Run check for solver counterexamples and their source replay status.",
        "Runtime I/O and CLI process observations are evaluated by RT-01 conformance.",
    ]
    if scenarios_path is None or Path(scenarios_path).resolve() == DEFAULT_SCENARIOS.resolve():
        lines.append(
            "Scenario requirement source: examples/0003-calculator.md "
            f"{_digest(CALCULATOR_REQUIREMENTS.read_bytes())}"
        )
    for name, pair in sorted(definitions.items()):
        lines.extend(("", f"{name} — {program['functions'][name]['impl_hash']}"))
        for role in ("public", "provided"):
            value = pair[role]
            identity = contract.contract_hash(value)
            lines.extend((f"  {role} — {identity}", contract.checked_render(value).rstrip("\n")))
            for clause_id, pointer, _ in _clauses(value):
                span = f"{contract_pointer_prefix}/{name}/{role}/{pointer}"
                lines.append(f"  Source of {clause_id}: {_json(contract_input)} JSON Pointer {span}")

    lines.extend(("", "Scenario evidence (applicable clause IDs are scoped to the function and Contract role):"))
    lines.extend(_json(item) for item in scenarios)
    if previous_contracts_path is not None:
        previous_data = Path(previous_contracts_path).read_bytes()
        previous = contract_wire.loads(previous_data.decode("utf-8"))
        lines.extend(("", f"Contract diff baseline revision: {_digest(previous_data)}"))
        lines.append("Contract diff (clause references are assigned by role and position):")
        differences = list(_contract_differences(previous, definitions))
        lines.append("\n".join(map(_json, differences)) if differences else "No semantic changes.")
    return "\n".join(lines) + "\n"


def _digest_label(digest):
    value = "sha256:" + digest.removeprefix("sha256:")
    if not DIGEST.fullmatch(value):
        raise ValueError("invalid review input digest")
    return value


def packet_id(packet):
    """Identify the exact UTF-8 review bytes shown to a reviewer."""
    return _digest(packet.encode("utf-8"))


def _openssl(backend, *arguments, data=None):
    source = {"stdin": subprocess.DEVNULL} if data is None else {"input": data}
    return subprocess.run([backend, *arguments], capture_output=True, timeout=15, **source)


def _public_key_der(path, openssl, *, private_key=None):
    public_input = [] if private_key is not None else ["-pubin"]
    result = _openssl(
        openssl, "pkey", *public_input, "-in", str(path), "-pubout", "-outform", "DER", data=private_key,
    )
    key = result.stdout
    if result.returncode or len(key) != len(ED25519_SPKI_PREFIX) + 32 or not key.startswith(ED25519_SPKI_PREFIX):
        raise ValueError("expected an Ed25519 review key readable by OpenSSL")
    return key


def public_key_id(path, *, openssl="openssl"):
    """Hash the canonical public key encoding used by the trust policy."""
    return _digest(_public_key_der(path, openssl))


def _decision(identity, reviewer, key):
    if not isinstance(reviewer, str) or not reviewer.strip() or not reviewer.isprintable():
        raise ValueError("reviewer must be a nonempty printable identity")
    if not isinstance(identity, str) or not DIGEST.fullmatch(identity):
        raise ValueError("expected a SHA-256 review packet identity")
    return {"schema": RECEIPT_SCHEMA, "packet": identity, "decision": "approved", "reviewer": reviewer, "public_key_id": key}


def write_review_receipt(path, expected_packet_id, reviewer, private_key, *, openssl="openssl"):
    """Sign an approval of the exact displayed packet and write a new receipt."""
    # Keep one private key snapshot in memory. OpenSSL reads it from a pipe.
    key_data = Path(private_key).read_bytes()
    key_id = _digest(_public_key_der("/dev/stdin", openssl, private_key=key_data))
    decision = _decision(expected_packet_id, reviewer, key_id)
    with TemporaryDirectory(prefix="llmlang-sign-") as directory:
        message = Path(directory) / "decision"
        message.write_bytes(RECEIPT_DOMAIN + _json(decision).encode("utf-8"))
        result = _openssl(
            openssl, "pkeyutl", "-sign", "-rawin", "-inkey", "/dev/stdin", "-in", str(message), data=key_data,
        )
        if result.returncode or len(result.stdout) != 64:
            raise ValueError("OpenSSL failed to sign the review approval")
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(dict(decision, signature=result.stdout.hex()), stream, indent=2, sort_keys=True)
        stream.write("\n")


def verify_review_receipt(path, expected, reviewer, public_key, *, key_id=None, openssl="openssl"):
    """Require an approval from the configured key for this exact packet."""
    # DER is read once from OpenSSL and used for both identity and verification.
    key = _public_key_der(public_key, openssl)
    actual_key_id = _digest(key)
    if key_id is not None and actual_key_id != key_id:
        raise ValueError("trusted review public key does not match its configured identity")
    decision = _decision(expected, reviewer, actual_key_id)
    receipt = _parse_json(Path(path).read_bytes())
    if (not isinstance(receipt, dict) or set(receipt) != decision.keys() | {"signature"}
            or any(receipt[name] != value for name, value in decision.items())):
        raise ValueError("review receipt does not approve the exact packet with the trusted reviewer and key")
    signature = receipt["signature"]
    if not isinstance(signature, str) or not re.fullmatch(r"[0-9a-f]{128}", signature):
        raise ValueError("invalid Ed25519 review signature encoding")
    with TemporaryDirectory(prefix="llmlang-review-") as directory:
        root = Path(directory)
        key_path, message, signature_path = (root / "key.der", root / "decision", root / "signature")
        key_path.write_bytes(key)
        message.write_bytes(RECEIPT_DOMAIN + _json(decision).encode("utf-8"))
        signature_path.write_bytes(bytes.fromhex(signature))
        result = _openssl(
            openssl, "pkeyutl", "-verify", "-rawin", "-pubin", "-keyform", "DER", "-inkey", str(key_path),
            "-in", str(message), "-sigfile", str(signature_path),
        )
        if result.returncode:
            raise ValueError("Ed25519 review signature verification failed")
