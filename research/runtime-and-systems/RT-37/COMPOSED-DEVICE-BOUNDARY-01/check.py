"""Compare typed device admission across register protocol, IRQ closure and DMA handback."""

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from itertools import product
import json
from pathlib import Path


@dataclass(frozen=True)
class DeviceUse:
    exact_profile: bool
    capability: bool
    volatile_word: bool
    register_effect: str
    irq_path: str
    exact_lease: bool
    in_bounds: bool
    completed: bool
    quiescent: bool
    synchronized_acquire: bool


def admit(request):
    if not (request.exact_profile and request.capability and request.volatile_word):
        return "refused"
    if request.register_effect != "write-one-mask":
        return "refused"
    if not all((request.exact_lease, request.in_bounds, request.completed, request.quiescent,
                request.synchronized_acquire)):
        return "refused"
    if request.irq_path == "nested-block":
        return "refused"
    if request.irq_path == "unresolved":
        return "unknown"
    return "eligible"


def controls(request):
    structural = request.exact_profile and request.capability and request.volatile_word
    ownership = (request.exact_lease and request.in_bounds and request.completed
                 and request.quiescent and request.synchronized_acquire)
    return {
        "address-and-access-only": structural and ownership and request.irq_path == "ack",
        "root-handler-only": structural and ownership and request.register_effect == "write-one-mask",
        "dma-completion-only": (structural and request.completed and request.register_effect == "write-one-mask"
                                and request.irq_path == "ack"),
    }


def main():
    bits = (False, True)
    register_effects = ("write-one-mask", "read-modify-write", "set-alias")
    irq_paths = ("ack", "nested-block", "unresolved")
    accepted_conditions = (True, True, True, "write-one-mask", "ack", True, True, True, True, True)
    unverifiable_conditions = (True, True, True, "write-one-mask", "unresolved", True, True, True, True, True)
    outcomes = Counter()
    disagreement = {}
    witnesses = {}
    for fields in product(bits, bits, bits, register_effects, irq_paths, bits, bits, bits, bits, bits):
        request = DeviceUse(*fields)
        expected = {accepted_conditions: "eligible", unverifiable_conditions: "unknown"}.get(fields, "refused")
        assert admit(request) == expected
        outcomes[expected] += 1
        for policy, allowed in controls(request).items():
            table = disagreement.setdefault(policy, Counter())
            table[f"allow={allowed}/{expected}"] += 1
            if allowed and expected != "eligible" and policy not in witnesses:
                witnesses[policy] = dict(zip(DeviceUse.__dataclass_fields__, fields))
    assert outcomes == {"refused": 2302, "unknown": 1, "eligible": 1}
    return {"outcomes": outcomes, "control_dispositions": disagreement, "example_admissions": witnesses,
            "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, sort_keys=True))
