"""Distinguish coroutine dispatch, suspensions and kernel context-switch counts."""

from collections import Counter
from hashlib import sha256
from itertools import product, zip_longest
import json
from pathlib import Path
import platform
import resource
import sys
import time


class Pause:
    def __await__(self):
        yield "pending"


class Cancelled(Exception):
    pass


async def worker(body, cleanup):
    try:
        for _ in range(body):
            await Pause()
    finally:
        for _ in range(cleanup):
            await Pause()


def execute(body, cleanup, peer_body, cancel):
    routes = {"main": worker(body, cleanup), "peer": worker(peer_body, 0)}
    terminal = {}
    observations = []
    main_steps = body + cleanup + 1 if not cancel else cleanup + 2
    for left, right in zip_longest(["main"] * main_steps, ["peer"] * (peer_body + 1)):
        for actor in (left, right):
            if actor is None:
                continue
            coroutine = routes[actor]
            previous = [outcome for owner, outcome in observations if owner == actor]
            try:
                if actor == "main" and cancel and previous == ["pending"]:
                    outcome = coroutine.throw(Cancelled())
                else:
                    outcome = coroutine.send(None)
            except StopIteration:
                outcome = "completed"
            except Cancelled:
                outcome = "cancelled"
            if outcome != "pending":
                assert actor not in terminal
                terminal[actor] = outcome
            observations.append((actor, outcome))
    assert terminal == {"main": "cancelled" if cancel else "completed", "peer": "completed"}
    actors = [actor for actor, _ in observations]
    dispatch = Counter(actors)
    suspended = Counter(actor for actor, outcome in observations if outcome == "pending")
    owner_change = Counter(next_ for prev, next_ in zip(actors, actors[1:]) if prev != next_)
    return {
        "dispatch": dict(dispatch), "suspensions": dict(suspended),
        "logical_owner_changes": dict(owner_change), "terminal": terminal,
        "hierarchy": {"root_dispatch": sum(dispatch.values()),
                      "root_suspensions": sum(suspended.values())},
    }


def verify(body, cleanup, peer_body, cancel):
    result = execute(body, cleanup, peer_body, cancel)
    main_pauses = (1 if cancel else body) + cleanup
    expected_dispatch = {"main": main_pauses + 1, "peer": peer_body + 1}
    expected_pending = {name: count - 1 for name, count in expected_dispatch.items() if count > 1}
    paired = min(expected_dispatch.values())
    expected_changes = {"peer": paired}
    changes_to_main = min(expected_dispatch["main"] - 1, expected_dispatch["peer"])
    if changes_to_main:
        expected_changes["main"] = changes_to_main
    assert result["dispatch"] == expected_dispatch
    assert result["suspensions"] == expected_pending
    assert result["logical_owner_changes"] == expected_changes
    assert result["hierarchy"] == {"root_dispatch": main_pauses + peer_body + 2,
                                   "root_suspensions": main_pauses + peer_body}
    return result


def sleeping_thread():
    before = resource.getrusage(resource.RUSAGE_THREAD)
    time.sleep(0.02)
    after = resource.getrusage(resource.RUSAGE_THREAD)
    assert after.ru_nvcsw > before.ru_nvcsw
    return {"kernel_voluntary_switch_increased": True, "coroutine_dispatched": False}


if __name__ == "__main__":
    rows = {f"{body}/{cleanup}/{peer}/{cancel}": verify(body, cleanup, peer, cancel)
            for body, cleanup, peer, cancel in product((1, 2, 4), (0, 1, 3), (0, 3), (False, True))}
    print(json.dumps({"platform": platform.system(), "python": sys.version.split()[0],
                      "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
                      "rows": rows, "kernel_control": sleeping_thread()}, indent=2, sort_keys=True))
