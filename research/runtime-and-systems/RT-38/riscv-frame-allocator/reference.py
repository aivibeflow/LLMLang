from collections import Counter
from itertools import chain, product

COMMAND_COUNT = 17
TARGETED = (0, 1, 2, 3, 12, 11, 3)
RECORD_SIZE = 10


def sequences():
    return chain(product(range(COMMAND_COUNT), repeat=3), (TARGETED,))


def reference_steps(commands, *, zero_on_release):
    """Abstract ownership uses slots and an explicit set of available frame IDs."""
    available = {1, 2, 3}
    assigned = {}
    for command in commands:
        scrub = 0
        if command == 16:
            status = "I"
        elif command >= 12:
            slot = command - 12
            released = assigned.pop(slot, None)
            status = "N" if released is None else "R"
            if released is not None:
                available.add(released)
                scrub = int(zero_on_release)
        else:
            fault, slot = divmod(command, 4)
            if slot in assigned:
                status = "E"
            elif not available:
                status = "F"
            else:
                status = ("A", "B", "L")[fault]
                scrub = int(fault != 1 and not zero_on_release)
                if fault == 0:
                    frame = min(available)
                    available.remove(frame)
                    assigned[slot] = frame

        mappings = "".join(str(assigned.get(slot, 0)) for slot in range(4))
        ownership = "".join("0" if frame in available else "2" for frame in range(1, 4))
        yield f"{status}{mappings}{ownership}{scrub}0"


def violations(record):
    status, slots, ownership, scrub, dirty = record[0], record[1:5], record[5:8], record[8], record[9]
    if status not in "AEFBLNRI" or any(frame not in "0123" for frame in slots):
        raise ValueError(f"Invalid status or PTE marker in {record!r}")
    if any(state not in "012" for state in ownership) or scrub not in "01" or dirty not in "01":
        raise ValueError(f"Invalid owner or work marker in {record!r}")
    aliases = Counter(slots.replace("0", ""))
    if dirty == "1":
        yield "dirty_at_publication"
    if "1" in ownership:
        yield "reservation_after_return"
    if any(amount > 1 for amount in aliases.values()):
        yield "aliased_frame"
    if {str(frame) for frame, state in enumerate(ownership, 1) if state == "2"} != set(aliases):
        yield "mapping_ownership_disagreement"
