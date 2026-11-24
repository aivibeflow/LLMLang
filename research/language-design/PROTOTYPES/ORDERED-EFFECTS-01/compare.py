"""Check ordered interprocedural effects in a closed Boolean fragment."""

from collections import Counter
from dataclasses import dataclass
from itertools import product


@dataclass(frozen=True)
class Outcome:
    exit: str
    events: tuple[str, ...]


PURE = Outcome("ok", ())


def compose(left, right):
    if left.exit != "ok":
        return left
    return Outcome(right.exit, left.events + right.events)


def summarize(program, name, environment):
    """Summarize under one projected entry valuation. None means unknown."""
    active = set()
    memo = {}

    def call(callee):
        if callee in active or callee not in program:
            return None
        if callee not in memo:
            active.add(callee)
            memo[callee] = walk(program[callee])
            active.remove(callee)
        return memo[callee]

    def walk(term):
        match term:
            case ("emit", event):
                return Outcome("ok", (event,))
            case ("fail", code):
                return Outcome(code, ())
            case ("if", flag, yes, no):
                return walk(yes if environment[flag] else no)
            case ("call", callee):
                return call(callee)
            case ("seq", *children):
                result = PURE
                for child in children:
                    if result is None or result.exit != "ok":
                        break
                    following = walk(child)
                    result = None if following is None else compose(result, following)
                return result
            case _:
                raise ValueError("outside the ordered effect fixture")

    return call(name)


def run(program, name, environment):
    """Execute with an explicit work list and an independent call limit."""
    todo = [("call", name)]
    events = []
    calls = 0
    while todo:
        op, *args = todo.pop()
        if op == "call":
            calls += 1
            if calls > 32 or args[0] not in program:
                return None
            todo.append(program[args[0]])
        elif op == "emit":
            events.append(args[0])
        elif op == "fail":
            return Outcome(args[0], tuple(events))
        elif op == "if":
            flag, yes, no = args
            todo.append(yes if environment[flag] else no)
        elif op == "seq":
            todo.extend(reversed(args))
        else:
            raise ValueError("outside the ordered effect fixture")
    return Outcome("ok", tuple(events))


def corpus():
    for flag, fail_first, swap, repeat, nested in product(
        ("use", "audit"), (False, True), (False, True), (False, True), (False, True),
    ):
        first = ("seq", ("emit", "reserve"), ("fail", "acquire-error")) if fail_first else ("emit", "reserve")
        second = ("seq", ("emit", "send"), ("emit", "send")) if repeat else ("emit", "send")
        left = ("if", "use", first, ("emit", "skip"))
        right = ("if", flag, second, ("emit", "audit"))
        order = ("right", "left") if swap else ("left", "right")
        yield {
            "entry": ("seq", *(("call", callee) for callee in order)),
            "left": ("call", "worker") if nested else left,
            "worker": left,
            "right": right,
        }, order


def check():
    envs = [{"use": use, "audit": audit} for use, audit in product((False, True), repeat=2)]
    counts = Counter()
    for program, (left, right) in corpus():
        actual = set()
        for env in envs:
            concrete = run(program, "entry", env)
            assert summarize(program, "entry", env) == concrete
            actual.add(concrete)
            counts["concrete-comparisons"] += 1
        independent = {
            compose(a, b) for a, b in product(
                {summarize(program, left, env) for env in envs},
                {summarize(program, right, env) for env in envs},
            )
        }
        assert actual <= independent
        counts["programs"] += 1
        counts["programs-with-spurious-traces"] += bool(independent - actual)
        counts["spurious-outcomes"] += len(independent - actual)

    witness, _ = next(corpus())
    impossible = Outcome("ok", ("reserve", "audit"))
    assert impossible not in {summarize(witness, "entry", env) for env in envs}
    left = summarize(witness, "left", {"use": True})
    right = summarize(witness, "right", {"use": False})
    assert compose(left, right) == impossible
    assert counts == {"concrete-comparisons": 128, "programs": 32,
                      "programs-with-spurious-traces": 16, "spurious-outcomes": 28}

    recursive = {"entry": ("if", "use", ("call", "entry"), ("emit", "done"))}
    absent = {"entry": ("if", "use", ("call", "unavailable"), ("emit", "done"))}
    for program in (recursive, absent):
        assert summarize(program, "entry", {"use": True}) is None
        assert run(program, "entry", {"use": True}) is None
        assert summarize(program, "entry", {"use": False}) == Outcome("ok", ("done",))
    sealed = {"entry": ("seq", ("emit", "prefix"), ("fail", "closed"), ("call", "unavailable"))}
    assert summarize(sealed, "entry", {}) == run(sealed, "entry", {}) == Outcome("closed", ("prefix",))
    a = run({"entry": ("seq", ("emit", "first"), ("emit", "second"))}, "entry", {})
    b = run({"entry": ("seq", ("emit", "second"), ("emit", "first"))}, "entry", {})
    assert set(a.events) == set(b.events) and a != b
    print(dict(counts))


if __name__ == "__main__":
    check()
