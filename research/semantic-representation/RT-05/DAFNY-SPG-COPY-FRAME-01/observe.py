"""Observe actual receiver accesses in the generated Dafny Python program."""

import json
import sys

sys.path.insert(0, sys.argv[1])
import _dafny
from module_ import default__

METHODS = ("SnapshotCopy", "DirectedCopy", "ForwardOnly", "SnapshotWithWrite")


class TracedArray(_dafny.Array):
    def __init__(self, values):
        super().__init__(0, len(values))
        self.arr[:] = values
        self.trace = []

    def __getitem__(self, index):
        value = super().__getitem__(index)
        positions = range(*index.indices(len(self))) if isinstance(index, slice) else (index,)
        self.trace.extend(("read", position) for position in positions)
        return value

    def __setitem__(self, index, value):
        super().__setitem__(index, value)
        self.trace.append(("write", index))


def observe(case):
    before, source, target, length = case
    results = {}
    for method in METHODS:
        buffer = TracedArray(before)
        getattr(default__, method)(buffer, source, target, length)
        results[method] = [buffer.arr, buffer.trace]
    return results


if __name__ == "__main__":
    print(json.dumps([observe(case) for case in json.load(sys.stdin)], separators=(",", ":")))
