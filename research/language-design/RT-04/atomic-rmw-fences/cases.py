from dataclasses import dataclass


@dataclass(frozen=True)
class Event:
    name: str
    kind: str
    location: str = ""
    value: int = 0
    order: str = "relaxed"

    @property
    def reads(self):
        return self.kind in ("load", "add")

    @property
    def writes(self):
        return self.kind in ("init", "store", "add")


@dataclass(frozen=True)
class Case:
    name: str
    threads: tuple
    outcome: dict
    allowed: bool
    sequential: bool | None = None
    adjacent_rmw: bool = True


def store(name, loc, value, order="relaxed"):
    return Event(name, "store", loc, value, order)


def add(name, loc, value=1, order="relaxed"):
    return Event(name, "add", loc, value, order)


def load(name, loc, order="relaxed"):
    return Event(name, "load", loc, order=order)


def fence(name, order):
    return Event(name, "fence", order=order)


def cases():
    increments = ((add("first", "counter"),), (add("second", "counter"),))
    yield Case("rmw_same_old_value", increments, {"first": 0, "second": 0}, False)
    yield Case("broken_rmw_same_old_value", increments, {"first": 0, "second": 0}, True, False, adjacent_rmw=False)
    yield Case("rmw_serialize", increments, {"first": 1, "second": 0}, True, True)
    wrap = ((store("seed", "counter", 255), add("inc", "counter")), (load("counter_read", "counter"),))
    yield Case("rmw_wrap", wrap, {"inc": 255, "counter_read": 0}, True, True)

    publication = (store("payload", "data", 42), store("publish", "flag", 1, "release"))
    relay = (add("inc", "flag"),)
    observer = (load("flag_read", "flag", "acquire"), load("data_read", "data"))
    stale = {"inc": 1, "flag_read": 2, "data_read": 0}
    yield Case("release_sequence", (publication, relay, observer), stale, False)
    yield Case("release_sequence_fresh", (publication, relay, observer), {**stale, "data_read": 42}, True, True)
    plain = (store("plain", "flag", 3),)
    yield Case("plain_write_breaks_sequence", (publication, relay, observer, plain),
               {"inc": 3, "flag_read": 4, "data_read": 0}, True)
    release_observer = (load("flag_read", "flag"), load("data_read", "data"))
    yield Case("missing_acquire_on_relay", (publication, relay, release_observer), stale, True, False)

    release_fence = (store("payload", "data", 42), fence("release_fence", "release"), store("publish", "flag", 1))
    acquire_fence = (load("flag_read", "flag"), fence("acquire_fence", "acquire"), load("data_read", "data"))
    stale = {"flag_read": 1, "data_read": 0}
    yield Case("fence_to_fence", (release_fence, acquire_fence), stale, False)
    yield Case("fence_to_fence_fresh", (release_fence, acquire_fence), {**stale, "data_read": 42}, True, True)
    yield Case("release_fence_to_acquire_load", (release_fence, observer), stale, False)
    yield Case("release_store_to_acquire_fence", (publication, acquire_fence), stale, False)
    late_release = (release_fence[0], release_fence[2], release_fence[1])
    yield Case("late_release_fence", (late_release, acquire_fence), stale, True, False)
    early_acquire = (acquire_fence[1], acquire_fence[0], acquire_fence[2])
    yield Case("early_acquire_fence", (release_fence, early_acquire), stale, True, False)
    yield Case("removed_acquire_fence", (release_fence, release_observer), stale, True, False)
    yield Case("fence_through_release_sequence", (release_fence, relay, acquire_fence),
               {"inc": 1, "flag_read": 2, "data_read": 0}, False)

    helper = (add("relay", "flag", order="acq_rel"), load("relay_data", "data"))
    yield Case("acquire_rmw_reads_release", (publication, helper),
               {"relay": 1, "relay_data": 0}, False)
    weak_helper = (add("relay", "flag"), load("relay_data", "data"))
    yield Case("relaxed_rmw_reads_release", (publication, weak_helper),
               {"relay": 1, "relay_data": 0}, True, False)
