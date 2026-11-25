"""Compare four scoped execution profiles on one finite resource workload."""

import argparse
from collections import Counter, deque
from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import permutations, product
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BASE = "99c6d98f"
DECLARATIONS = (
    "CORE-LANGUAGE-SEMANTICS.md",
    "RT-03-SEMANTIC-PROFILES-FOR-SYNTHESIS-2026-11-25.md",
    "RT-03-04-SHARED-SEMANTICS-CORPUS.md",
)
ORDERS = tuple(permutations("abx"))
ORDERED = ("a", "x", "b")


@dataclass(frozen=True)
class Job:
    delta: int
    retain: bool


@dataclass(frozen=True)
class Input:
    initial: int
    jobs: tuple[Job, Job]
    target: str
    permitted: frozenset[str]

    def job(self, role):
        return self.jobs["ab".index(role)]


@dataclass(frozen=True)
class Result:
    balance: int
    trace: tuple
    retained: frozenset[str]


def describe_pure(case, order):
    """Interpret immutable inputs into an outcome and ordered effect description."""
    balance = case.initial
    trace = ()
    cancelled = frozenset()
    finished = frozenset()
    retained = frozenset()
    for command in order:
        if command == "x":
            accepted = case.target not in finished
            cancelled = cancelled | {case.target} if accepted else cancelled
            trace += (("cancel", case.target, accepted),)
            continue
        job = case.job(command)
        candidate = balance + job.delta
        if command in cancelled:
            outcome = "cancelled"
        elif command not in case.permitted:
            outcome = "denied"
        elif candidate < 0:
            outcome = "underflow"
        else:
            outcome = "committed"
            trace += (("write", command, balance, candidate),)
            balance = candidate
        finished = finished | {command}
        retained = retained | {command} if job.retain else retained
        trace += (("settle", command, outcome, "returned" if job.retain else "released"),)
    return Result(balance, trace, frozenset(retained))


class MutableOwner:
    """Sequential owner used in the imperative and actor receiver profiles."""

    def __init__(self, case):
        self.balance = case.initial
        self.case = case
        self.outstanding = set("ab")
        self.cancelled = set()
        self.retained = set()
        self.trace = []

    def accept(self, command):
        if command == "x":
            target = self.case.target
            accepted = target in self.outstanding
            self.trace.append(("cancel", target, accepted))
            if accepted:
                self.cancelled.add(target)
            return

        self.outstanding.remove(command)
        job = self.case.job(command)
        result = "committed"
        if command in self.cancelled:
            result = "cancelled"
        elif command not in self.case.permitted:
            result = "denied"
        elif self.balance < -job.delta:
            result = "underflow"
        else:
            previous = self.balance
            self.balance += job.delta
            self.trace.append(("write", command, previous, self.balance))
        if job.retain:
            self.retained.add(command)
        self.trace.append(("settle", command, result, "returned" if job.retain else "released"))

    def result(self):
        assert not self.outstanding
        return Result(self.balance, tuple(self.trace), frozenset(self.retained))


def imperative(case, order):
    owner = MutableOwner(case)
    for command in order:
        owner.accept(command)
    return owner.result()


def actor(case, delivery):
    # Three senders each offer one command. A single mailbox owner makes balance local.
    mailbox = deque(delivery)
    receiver = MutableOwner(case)
    while mailbox:
        receiver.accept(mailbox.popleft())
    return receiver.result()


def program(command, job, permitted):
    """Describe one command as effect requests before its interpretation."""
    if command == "x":
        yield "cancel", None
        return
    cancelled = yield "pending-cancellation", command
    if cancelled:
        outcome = "cancelled"
    elif not permitted:
        outcome = "denied"
    else:
        committed = yield "conditional-write", (command, job.delta)
        outcome = "committed" if committed else "underflow"
    yield "settle", (command, outcome, job.retain)


def effectful(case, order):
    balance = case.initial
    trace = []
    returned = set()
    settled = set()
    cancelled = False
    for command in order:
        request = program(command, None if command == "x" else case.job(command),
                          command in case.permitted)
        response = None
        while True:
            try:
                effect, arguments = request.send(response)
            except StopIteration:
                break
            response = None
            if effect == "cancel":
                cancelled = case.target not in settled
                trace.append(("cancel", case.target, cancelled))
            elif effect == "pending-cancellation":
                response = arguments == case.target and cancelled
            elif effect == "conditional-write":
                role, delta = arguments
                following = balance + delta
                response = following >= 0
                if response:
                    trace.append(("write", role, balance, following))
                    balance = following
            else:
                role, outcome, retain = arguments
                settled.add(role)
                if retain:
                    returned.add(role)
                trace.append(("settle", role, outcome, "returned" if retain else "released"))
    return Result(balance, tuple(trace), frozenset(returned))


def check_trace(case, order, observed):
    """Independently check the contextual requirements of one candidate observation."""
    grouped = iter(observed.trace)
    balance = case.initial
    retained = set()
    for index, command in enumerate(order):
        event = next(grouped)
        if command == "x":
            assert event == ("cancel", case.target, case.target in order[index + 1:])
            continue
        job = case.job(command)
        denied = command not in case.permitted
        cancelled = order.index("x") < index and command == case.target
        allowed = not denied and not cancelled and balance + job.delta >= 0
        if allowed:
            assert event == ("write", command, balance, balance + job.delta)
            balance += job.delta
            event = next(grouped)
        reason = ("cancelled" if cancelled else "denied" if denied else
                  "committed" if allowed else "underflow")
        assert event == ("settle", command, reason, "returned" if job.retain else "released")
        if job.retain:
            retained.add(command)
    assert next(grouped, None) is None
    assert (observed.balance, observed.retained) == (balance, retained)


def git(*args):
    return subprocess.check_output(["git", "-C", str(REPO), *args], text=True).strip()


def static_pins():
    directory = HERE.parent
    paths = [directory / name for name in DECLARATIONS]
    result = {}
    for path in paths:
        relative = str(path.relative_to(REPO))
        blob = git("rev-parse", f"{BASE}:{relative}")
        assert blob == git("hash-object", relative)
        result[relative] = blob
    return result


def encode_result(result):
    return [result.balance, result.trace, sorted(result.retained)]


def compare():
    options = [Job(*pair) for pair in product((-2, -1, 1, 2), (False, True))]
    rows = []
    examples = {}
    counts = Counter()
    same_balance_distinct_pairs = Counter()
    for initial, a, b, target, permitted in product(
        (0, 1, 2), options, options, "ab", ("", "a", "b", "ab")
    ):
        case = Input(initial, (a, b), target, frozenset(permitted))
        candidates = []
        for order in ORDERS:
            plain, imperative_result, effect_result = (
                route(case, order) for route in (describe_pure, imperative, effectful)
            )
            receiver = actor(case, order)
            assert plain == imperative_result == effect_result == receiver
            check_trace(case, order, receiver)
            candidates.append(receiver)
        ordered = candidates[ORDERS.index(ORDERED)]
        assert ordered in candidates
        assert len(set(candidates)) > 1
        balances = {result.balance for result in candidates}
        category = "actor_same_scalar_multi_trace" if len(balances) == 1 else "actor_multi_scalar"
        counts[category] += 1
        pairs = sum(
            left.balance == right.balance and left != right
            for index, left in enumerate(candidates)
            for right in candidates[index + 1:]
        )
        same_balance_distinct_pairs[pairs] += 1
        counts["same_scalar_distinct_schedule_pairs"] += pairs
        counts["workloads"] += 1
        counts["cross_profile_observations"] += 4 * len(ORDERS)
        payload = [encode_result(result) for result in candidates]
        digest = sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()
        row = [initial, a.delta, int(a.retain), b.delta, int(b.retain), target, permitted,
               len(balances), len(set(candidates)), pairs, digest]
        rows.append(row)
        if category not in examples:
            examples[category] = {"matrix_row": len(rows) - 1, "observations_in_schedule_order": payload}
    return rows, counts, same_balance_distinct_pairs, examples


def negative_controls():
    case = Input(0, (Job(1, True), Job(1, False)), "a", frozenset("ab"))
    order = ORDERED
    accepted = describe_pure(case, order)
    altered = {
        "reordered_first_write_and_cleanup": replace(accepted, trace=(
            accepted.trace[1], accepted.trace[0], *accepted.trace[2:]
        )),
        "scalar_only": replace(accepted, trace=()),
        "lost_returned_lease": replace(accepted, retained=frozenset()),
        "removed_cancellation_record": replace(accepted, trace=tuple(
            event for event in accepted.trace if event[0] != "cancel"
        )),
    }
    results = {}
    for name, candidate in altered.items():
        try:
            check_trace(case, order, candidate)
        except (AssertionError, StopIteration):
            results[name] = {"scalar_matches": candidate.balance == accepted.balance,
                             "full_contract_refused": True}
        else:
            raise ValueError(f"Weaker observation accepted: {name}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rows, counts, grouped, examples = compare()
    result = {
        "input_revision": git("rev-parse", BASE), "input_blobs": static_pins(),
        "python": sys.version.split()[0], "schedules": ["".join(order) for order in ORDERS],
        "reference_order": "".join(ORDERED), "counts": counts, "pairs_by_same_scalar_count": grouped,
        "negative_controls": negative_controls(), "examples": examples, "rows": rows,
        "columns": ["initial", "a_delta", "a_retain", "b_delta", "b_retain", "cancel_target",
                    "grants", "distinct_scalars", "distinct_full_traces",
                    "same_scalar_distinct_schedule_pairs", "observation_sha256"],
    }
    args.out.write_text(json.dumps(result, separators=(",", ":")) + "\n")
