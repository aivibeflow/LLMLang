"""Check bounded adoption readiness and fail-closed cutover prerequisites."""

from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform


SHADOW = ("immutable_baseline", "typed_unit", "independent_observations", "effect_isolation")
CANARY = (*SHADOW, "representative_workload", "bounded_operational_cost", "reversible_state",
          "observed_rollback", "human_authority")


def readiness(facts):
    if all(facts.get(name) == "checked" for name in CANARY):
        return "canary-candidate"
    if all(facts.get(name) == "checked" for name in SHADOW):
        return "effect-free-shadow-candidate"
    return "study-only"


def collect():
    profiles = Counter()
    all_true = dict.fromkeys(CANARY, "checked")
    withheld = {}
    for name in CANARY:
        withheld[name] = readiness({**all_true, name: "unknown"})
    assert all(level != "canary-candidate" for level in withheld.values())
    for states in product(("checked", "unknown", "failed"), repeat=len(CANARY)):
        facts = dict(zip(CANARY, states, strict=True))
        expected = ("study-only" if any(value != "checked" for value in states[:4]) else
                    "canary-candidate" if states[4:] == ("checked",) * 5 else "effect-free-shadow-candidate")
        observed = readiness(facts)
        assert expected == observed
        profiles[observed] += 1
    # A checked synthetic case is insufficient evidence for the unverified project binding.
    archived_fixture_scope = {**all_true, "representative_workload": "unknown",
                              "bounded_operational_cost": "unknown", "observed_rollback": "unknown",
                              "human_authority": "unknown"}
    assert readiness(archived_fixture_scope) == "effect-free-shadow-candidate"
    candidate_only = dict.fromkeys(CANARY, "unknown")
    assert readiness(candidate_only) == "study-only"
    return {"python": platform.python_version(), "total_profiles": sum(profiles.values()), "profiles": profiles,
            "unknown_single_fact": withheld,
            "bounded_fixture_with_unverified_production_scope": readiness(archived_fixture_scope),
            "unbound_candidate": readiness(candidate_only),
            "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(collect(), sort_keys=True, indent=2))
