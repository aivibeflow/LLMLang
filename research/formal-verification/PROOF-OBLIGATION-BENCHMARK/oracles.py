"""Finite reference/mutant experiments; no proof backend and no unbounded proof."""
from collections import Counter, deque
from itertools import product, combinations
from functools import reduce
import operator


def arrays():
    return [a for n in range(4) for a in product((-1, 0, 1), repeat=n)]


def sum_all(mut):
    for a in arrays():
        # Oracle: count occurrences of each possible value.
        expected = a.count(1) - a.count(-1)
        actual = reduce(operator.add, a[:-1] if mut else a, 0)
        yield a, actual == expected


def first_match(mut):
    for a, t in product(arrays(), (-1, 0, 1)):
        indices = range(len(a)-1, -1, -1) if mut else range(len(a))
        i = next((i for i in indices if a[i] == t), -1)
        ok = (t not in a) if i == -1 else (0 <= i < len(a) and a[i] == t and t not in a[:i])
        yield (a, t), ok


def sort(mut):
    for a in arrays():
        b = sorted(set(a) if mut else a)
        yield a, all(x <= y for x, y in zip(b, b[1:])) and Counter(b) == Counter(a)


def reverse(mut):
    for a in arrays():
        for s in range(len(a)+1):
            for e in range(s, len(a)+1):
                b = a[::-1] if mut else a[:s] + a[s:e][::-1] + a[e:]
                ok = len(b) == len(a) and all(b[i] == a[s+e-1-i if s <= i < e else i] for i in range(len(a)))
                yield (a, s, e), ok


def rotate(mut):
    def inorder(node):
        if node is None:
            return ()
        key, left, right = node
        return inorder(left) + (key,) + inorder(right)
    for a, b, c in combinations(range(-2, 3), 3):
        original = (b, (a, None, None), (c, None, None))
        key, left, right = original
        rk, rl, rr = right
        rotated = (rk, (key, None if mut else left, rl), rr)
        yield (a, b, c), rotated[0] == c and inorder(rotated) == (a,b,c)


def cleanup(mut):
    for n, fail in product(range(4), (False, True)):
        acquired = list(range(n))
        released = list(reversed(acquired[:-1] if mut and fail else acquired))
        trace = [('acquire', x) for x in acquired] + [('release', x) for x in released]
        live, seen, ok = set(), set(), True
        for action, x in trace:
            if action == 'acquire':
                ok &= x not in seen
                live.add(x)
                seen.add(x)
            else:
                ok &= x in live
                live.discard(x)
        yield (n, fail), ok and not live and seen == set(range(n))


def transfer(mut):
    for a,b,x,fail in product(range(4), range(4), range(5), (False,True)):
        if x > a:
            result = (a,b)
        elif fail:
            result = (a-x,b) if mut else (a,b)
        else:
            result = (a-x,b+x)
        p,q = result
        ok = (result == (a,b)) if fail or x > a else (p == a-x and q == b+x and p >= 0 and p+q == a+b)
        yield (a,b,x,fail), ok


def queue(mut):
    for n in range(5):
        for ops in product((0,1,None), repeat=n):
            q, out = deque(), []
            for op in ops:
                if op is None:
                    out.append((q.pop() if mut else q.popleft()) if q else None)
                else:
                    q.append(op)
            # Oracle: match each dequeue to the earliest unmatched enqueue position.
            used, expected = set(), []
            for i, op in enumerate(ops):
                if op is None:
                    j = next((j for j in range(i) if ops[j] is not None and j not in used), None)
                    expected.append(None if j is None else ops[j])
                    if j is not None:
                        used.add(j)
            remaining = [v for j,v in enumerate(ops) if v is not None and j not in used]
            yield ops, out == expected and list(q) == remaining


def progress(mut):
    for ticks in product((False,True), repeat=3):
        if not any(ticks[:2]):
            continue
        done = None
        for i, service in enumerate(ticks, 1):
            if service and (not mut or i > 2):
                done = i
                break
        yield ticks, done is not None and done <= 2


def algebra(mut):
    for a,b,c in product(range(-2,3), repeat=3):
        result = a + (b-c if mut else b+c)
        yield (a,b,c), result == (a+b)+c


def isolation(mut):
    def observe(public, secret):
        return public + secret if mut else public
    for p,s,t in product(range(3), repeat=3):
        yield (p,s,t), observe(p,s) == observe(p,t) == p


def checked(mut):
    for a,b in product(range(-8,8), repeat=2):
        # Candidate models signed overflow by operand signs and wrapped value.
        wrapped = ((a+b+8) % 16)-8
        overflow = (a >= 0 and b >= 0 and wrapped < 0) or (a < 0 and b < 0 and wrapped >= 0)
        actual = wrapped if mut or not overflow else None
        expected = a+b if -8 <= a+b <= 7 else None
        yield (a,b), actual == expected


ORACLES = {f.__name__: f for f in (sum_all, first_match, sort, reverse, rotate, cleanup, transfer, queue, progress, algebra, isolation, checked)}
