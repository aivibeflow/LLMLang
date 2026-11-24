from collections import deque
from itertools import count

from request_vectors import A, B


def replay(*, generation_checked, limit):
    inbox = deque(maxlen=1)
    guest = None
    handles = count(1)
    trace = []
    scheduled = deque([("A", iter(A)), ("B", iter(B))])
    while scheduled:
        principal, commands = scheduled.popleft()
        request = next(commands, None)
        if request is None:
            trace.append(principal.lower())
            continue
        operation, token, octet = request
        status = "I"
        if principal == "A" and operation == 3:
            rights = {1: {"send"}, 2: {"receive"}, 3: {"send", "receive"}}.get(octet)
            if not rights:
                status = "D"
            elif guest:
                status = "F"
            else:
                generation = next(handles)
                if generation <= limit:
                    guest = (generation, rights)
                    status = "G"
                else:
                    status = "O"
        elif principal == "A" and operation == 4:
            status = "R" if guest is not None else "N"
            guest = None
        elif operation in (1, 2):
            action = {1: "send", 2: "receive"}[operation]
            if principal == "B" and not guest:
                status = "N"
            elif principal == "B" and generation_checked and token != guest[0]:
                status = "S"
            elif principal == "B" and action not in guest[1]:
                status = "D"
            elif action == "send":
                status = "F" if inbox else "A"
                if not inbox:
                    inbox.append(chr(octet))
            else:
                status = inbox.popleft() if inbox else "E"
        trace.append(f"{principal}{status}")
        scheduled.append((principal, commands))
    return trace + ["!"]
