"""Execute the checked fixture on CPython without importing the CFG interpreter."""

import dis
import sys


class Fault(Exception):
    pass


def execute(source, flags, close_errors):
    log = []
    slots = {}
    staged = []

    def observe(event, *payload):
        frame = sys._getframe(2)
        span = positions[frame.f_lasti]
        log.append([list(span), event, *payload])

    def probe(label, value):
        observe("probe", label, value)
        return value

    def release(label):
        if slots[label] != "live":
            raise AssertionError("Closing a resource that is not live")
        ok = not close_errors[label]
        observe("close", label, ok)
        if not ok:
            slots[label] = "debt"
            raise Fault(f"close:{label}")
        slots[label] = "released"

    def acquire(label):
        if label in slots:
            raise AssertionError("Acquiring two resources for one slot")
        observe("open", label)
        slots[label] = "live"

    def stage(label):
        observe("stage", label)
        staged.append(label)
        return label

    def fail(label):
        observe("fail", label)
        raise Fault(label)

    def emit(label):
        observe("emit", label)

    primitives = {
        "__builtins__": {}, "open_slot": acquire, "close_slot": release,
        "probe": probe, "stage": stage, "fail": fail, "emit": emit,
    }
    exec(compile(source, "fixture.llprobe.py", "exec"), primitives)
    entry = primitives["entry"]
    positions = {instruction.offset: instruction.positions
                 for instruction in dis.get_instructions(entry, show_caches=True)}

    causes = []
    result = None
    handle = "none"
    try:
        result = entry(flags["x"], flags["y"])
        assert staged == [result]
        handle = "caller"
    except Fault as fault:
        if staged:
            assert len(staged) == 1
            handle = "pending"
        current = fault
        while current is not None:
            assert type(current) is Fault
            causes.append(str(current))
            current = current.__context__
        causes.reverse()

    return {"trace": log, "result": result, "errors": causes, "slots": slots, "handle": handle}
