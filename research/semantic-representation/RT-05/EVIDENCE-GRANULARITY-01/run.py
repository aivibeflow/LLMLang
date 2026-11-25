"""Compare immutable evidence layouts while checking exact subject bindings."""

from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path
import platform

CHECKER = "exact-finite-row-checker-v1"
LAYOUTS = ("bundle", "embedded_per_receipt", "shared_payload")


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def put(objects, value):
    payload = encode(value)
    key = sha(payload)
    objects[key] = payload
    return key


def get(objects, key):
    blob = objects[key]
    if sha(blob) != key:
        raise ValueError("stored object digest disagrees")
    return json.loads(blob)


@dataclass(frozen=True)
class Claim:
    slot: int
    revision: int
    operation: str
    domain_size: int

    @property
    def identity(self):
        return sha(encode({"kind": "fixture-claim", **asdict(self)}))


def implementation(claim, i):
    return i * 2 if claim.operation == "double" else i + 1


def certificate(claim):
    return {"rows": [[i, implementation(claim, i)] for i in range(claim.domain_size)]}


def check_rows(claim, payload):
    if [row[0] for row in payload["rows"]] != list(range(claim.domain_size)):
        return False
    # Separately state the two bounded predicates.
    if claim.operation == "double":
        return all(output - i == i for i, output in payload["rows"])
    return all(output - 1 == i for i, output in payload["rows"])


def create_receipt(claim, payload):
    assert check_rows(claim, payload)
    return {"claim": claim.identity, "checker": CHECKER, "payload": sha(encode(payload))}


def admit(claim, record, payload):
    if record is None or record["claim"] != claim.identity or record["checker"] != CHECKER:
        return False
    return record["payload"] == sha(encode(payload)) and check_rows(claim, payload)


def pack(layout, claims):
    objects = {}
    bodies = []
    for claim in claims:
        payload = certificate(claim)
        receipt = create_receipt(claim, payload)
        if layout == "shared_payload":
            payload_ref = put(objects, payload)
            assert payload_ref == receipt["payload"]
            bodies.append(put(objects, receipt))
        else:
            embedded = {"receipt": receipt, "payload": payload}
            bodies.append(put(objects, embedded) if layout == "embedded_per_receipt" else embedded)
    root = put(objects, {"layout": layout, "entries": bodies})
    return root, objects


def validate(root, objects, claims):
    bundle = get(objects, root)
    entries = bundle["entries"]
    if len(entries) != len(claims):
        return False
    for claim, entry in zip(claims, entries):
        if bundle["layout"] == "shared_payload":
            receipt = get(objects, entry)
            payload = get(objects, receipt["payload"])
        else:
            embedded = get(objects, entry) if bundle["layout"] == "embedded_per_receipt" else entry
            receipt, payload = embedded["receipt"], embedded["payload"]
        if not admit(claim, receipt, payload):
            return False
    return True


def measure(layout, before, changed):
    old_root, old_objects = pack(layout, before)
    new_root, new_objects = pack(layout, changed)
    assert validate(old_root, old_objects, before) and validate(new_root, new_objects, changed)
    assert old_root != new_root and not validate(old_root, old_objects, changed)
    added = new_objects.keys() - old_objects.keys()
    return {"old_objects": len(old_objects), "old_bytes": sum(map(len, old_objects.values())),
            "new_unique_objects": len(added), "new_unique_bytes": sum(len(new_objects[k]) for k in added)}


def main():
    measurements = {}
    for count in (4, 16, 64, 256):
        original = tuple(Claim(index, 1, "double", 64) for index in range(count))
        revisions = {
            "subject_only": (*original[:-1], replace(original[-1], revision=2)),
            "new_payload": (*original[:-1], replace(original[-1], revision=2, operation="increment")),
        }
        measurements[count] = {label: {layout: measure(layout, original, changed) for layout in LAYOUTS}
                               for label, changed in revisions.items()}
    for scope in measurements.values():
        for result in scope.values():
            assert result["shared_payload"]["new_unique_bytes"] < result["bundle"]["new_unique_bytes"]
        assert scope["subject_only"]["shared_payload"]["new_unique_objects"] == 2
        assert scope["new_payload"]["shared_payload"]["new_unique_objects"] == 3

    claim = Claim(0, 1, "double", 64)
    payload = certificate(claim)
    receipt = create_receipt(claim, payload)
    changed = replace(claim, revision=2)
    larger = replace(claim, domain_size=65)
    different_operation = replace(claim, revision=2, operation="increment")
    controls = {
        "same_payload_old_subject": admit(changed, receipt, payload),
        "same_payload_after_exact_recheck": admit(changed, create_receipt(changed, payload), payload),
        "same_payload_after_domain_expansion": admit(larger, receipt | {"claim": larger.identity}, payload),
        "same_payload_for_different_behavior": admit(
            different_operation, receipt | {"claim": different_operation.identity}, payload
        ),
        "payload_without_typed_receipt": admit(claim, None, payload),
        "wrong_checker": admit(claim, receipt | {"checker": "unapproved-fixture"}, payload),
    }
    assert list(controls.values()) == [False, True, False, False, False, False]
    return {"schema": "llmlang-rt05-evidence-granularity/1", "python": platform.python_version(),
            "runner_sha256": sha(Path(__file__).read_bytes()), "inputs_per_original_claim": 64,
            "storage_accounting": "logical uncompressed canonical JSON object bytes",
            "measurements": measurements, "exact_binding_controls": controls}


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
