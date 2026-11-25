"""Check scope-preserving resource grants against pinned Linux witnesses."""

from collections import Counter
from dataclasses import asdict, dataclass, fields
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform


HERE = Path(__file__).resolve().parent
PINS = {
    "LINUX-PERF-COUNTERS-01": "210ac910db0b52fd42afefb06adc747b9c3f8f43ca0eae365de8fd8145d918dd",
    "LINUX-MAPPING-BUDGET-01": "2dd126948d63844c55ae1dc13439da791eb9af18f367cfde87311db83022e67e",
    "LINUX-CPU-BUDGET-01": "dad2157550a16e89951dbf03da4d75c7bd9b51a72f79cf439e0c5272103f0bf1",
    "LINUX-SOCKET-BUDGET-01": "a0b9053c09d3478f152aa51c7f899bdd6bf6cdc1722939de506e74ead46d1ba2",
    "LINUX-FILE-BUDGET-01": "1255893f1312c680c06bb541341adf7d2734833beb255085d80e96d5998e1ea3",
}


def load_witnesses():
    def load(name, expected):
        path = HERE.parent / name / "evidence.json"
        raw = path.read_bytes()
        assert sha256(raw).hexdigest() == expected
        return json.loads(raw)

    perf, mapping, cpu, socket, file = [load(name, checksum) for name, checksum in PINS.items()]
    denied = perf["self_user_space_events"]
    assert denied["cycles"] == {"status": "unavailable", "errno": "EPERM"}
    assert perf["fallback"]["thread_cpu_at_least_20ms"]
    virtual = mapping["single"]
    assert virtual["discarded_resident_pages"] == 0 and virtual["second_after_discard"] == "ENOMEM"
    assert mapping["pair"]["over_hypothetical_group_allowance_bytes"] == 4 * 2**20
    local_cpu = cpu["cases"]["locally_admitted_pair"]
    assert local_cpu["each_below_own_limit"] and local_cpu["aggregate_exceeds_group_limit"]
    udp = socket["cases"]["udp_truncated"]
    assert udp["application_bytes"] == 4 and udp["removed_datagram_bytes"] == 16
    assert socket["cases"]["udp_competing_receive"]["original_invocation_dequeued_bytes"] == 16
    assert file["local_caps"]["root_overshoot_bytes"] == 2048
    assert file["brokered"]["settled"] == {"live": 3072, "pending": 0, "remaining": 1024}
    return {"pmu_cycles": "EPERM", "thread_cpu_control_passed": True,
            "discarded_mapping_resident_pages": virtual["discarded_resident_pages"],
            "mapping_refusal_after_discard": virtual["second_after_discard"],
            "local_process_cpu_exceeds_comparison_group": True,
            "udp_delivered_bytes": udp["application_bytes"],
            "udp_dequeued_bytes": udp["removed_datagram_bytes"],
            "local_file_limit_group_overshoot": file["local_caps"]["root_overshoot_bytes"]}


@dataclass(frozen=True)
class Key:
    metric: str
    scope: str
    effect_domain: str
    mode: str
    epoch: str


BOUNDARIES = {
    "thread_clock": Key("cpu-time", "thread", "native-thread", "observe", "linux-current"),
    "process_mapping": Key("virtual-address", "process", "mmap", "hard", "linux-current"),
    "file_broker": Key("logical-file-length", "task-tree", "brokered-write", "cooperative", "linux-current"),
    "udp_delivered": Key("application-bytes", "socket", "udp-receive", "observe", "linux-current"),
    "udp_dequeued": Key("dequeued-bytes", "socket", "udp-receive", "observe", "linux-current"),
}

AXES = {
    "metric": ("cpu-time", "cpu-cycles", "virtual-address", "resident-bytes", "logical-file-length",
               "disk-io-bytes", "application-bytes", "dequeued-bytes", "wire-bytes"),
    "scope": ("thread", "process", "task-tree", "socket"),
    "effect_domain": ("native-thread", "mmap", "brokered-write", "arbitrary-write", "udp-receive"),
    "mode": ("observe", "cooperative", "hard"),
    "epoch": ("linux-current", "linux-replaced", "portable"),
}


def admits(request, witness, capability, ignored=()):
    if "capability" not in ignored and not capability:
        return False
    return all(getattr(request, field.name) == getattr(witness, field.name)
               for field in fields(Key) if field.name not in ignored)


def negotiate(request, inventory, enabled, fallback=None):
    for name, witness in inventory.items():
        if admits(request, witness, name in enabled):
            return ("accepted", name)
    if fallback is not None:
        for name, witness in inventory.items():
            if admits(fallback, witness, name in enabled):
                return ("fallback-only", name)
    return ("unsupported", None)


def compare():
    keys = [Key(*parts) for parts in product(*AXES.values())]
    matches = {(tuple(asdict(key).values()), name) for name, key in BOUNDARIES.items()}
    admissions = Counter()
    mutant_false_grants = Counter()
    probes = 0
    for key, (name, witness), enabled in product(keys, BOUNDARIES.items(), (False, True)):
        expected = enabled and (tuple(asdict(key).values()), name) in matches
        result = admits(key, witness, enabled)
        assert expected is result
        admissions[name] += result
        probes += 1
        for omitted in (*AXES, "capability"):
            if admits(key, witness, enabled, (omitted,)) and not expected:
                mutant_false_grants[omitted] += 1
    assert set(admissions.values()) == {1}
    assert set(mutant_false_grants) == {*AXES, "capability"}

    fallback = BOUNDARIES["thread_clock"]
    cycles = Key("cpu-cycles", "thread", "native-thread", "hard", "linux-current")
    enabled = set(BOUNDARIES)
    assert negotiate(cycles, BOUNDARIES, enabled) == ("unsupported", None)
    assert negotiate(cycles, BOUNDARIES, enabled, fallback) == ("fallback-only", "thread_clock")
    assert negotiate(cycles, BOUNDARIES, enabled - {"thread_clock"}, fallback) == ("unsupported", None)
    assert negotiate(fallback, BOUNDARIES, enabled, fallback) == ("accepted", "thread_clock")
    mixed = Key("logical-file-length", "task-tree", "brokered-write", "hard", "linux-current")
    assert negotiate(mixed, BOUNDARIES, enabled) == ("unsupported", None)
    return {"requests": len(keys), "single_witness_probes": probes,
            "exact_admissions": dict(admissions), "false_grants_by_omitted_check": dict(mutant_false_grants),
            "controls": {"unavailable_cycles": "unsupported", "explicit_cpu_time": "fallback-only",
                         "revoked_fallback": "unsupported", "exact_thread_clock": "accepted",
                         "mixed_witnesses": "unsupported"}}


if __name__ == "__main__":
    receipt = {"python": platform.python_version(), "witnesses": PINS, "rechecked": load_witnesses(),
               "comparison": compare(), "modeled_boundaries": {k: asdict(v) for k, v in BOUNDARIES.items()},
               "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}
    print(json.dumps(receipt, indent=2, sort_keys=True))
