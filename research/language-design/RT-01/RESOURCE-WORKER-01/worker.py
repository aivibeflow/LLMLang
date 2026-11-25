"""A native-file worker behind two bounded Python request channels."""

import errno
import os
from pathlib import Path
from queue import Queue
import sys
from threading import Thread


class Work:
    def __init__(self, path, read_only):
        self.path = path
        self.read_only = read_only
        self.handle = None
        self.revoked = False
        self.outcome = None
        self.terminal = None

    def perform(self, operation, policy, label):
        if self.terminal is not None:
            return "already_" + self.terminal, False
        if operation == "start":
            if self.revoked:
                return "skipped", False
            assert self.handle is None
            self.handle = os.open(self.path, os.O_RDONLY if self.read_only else os.O_RDWR)
            assert os.path.lexists(f"/proc/self/fd/{self.handle}")
            return "started", False
        if operation == "cancel":
            if self.outcome is not None and policy != "early_terminal":
                return "too_late", False
            self.revoked = True
            return ("early_cancelled" if policy == "early_terminal" else "requested"), False
        if operation == "write":
            if self.handle is None or self.revoked and policy != "admission_only":
                return "blocked", False
            assert self.outcome is None
            try:
                assert os.write(self.handle, label.encode()) == 1
            except OSError as error:
                assert error.errno == errno.EBADF
                self.outcome = "io_failure"
                return "write_failed", False
            self.outcome = "ok"
            return "written", False
        assert operation == "settle"
        released = self.handle is not None
        if released:
            old_fd = self.handle
            os.close(old_fd)
            self.handle = None
            assert not os.path.lexists(f"/proc/self/fd/{old_fd}")
        self.terminal = "cancelled" if self.revoked else self.outcome
        assert self.terminal is not None
        return "settled_" + self.terminal, released


def run(root, policy, mask):
    jobs = [Work(root / f"job-{index}", bool(mask & (1 << index))) for index in range(2)]
    worker_queue = Queue(maxsize=1)
    responses = Queue(maxsize=1)
    inboxes = [Queue(maxsize=1) for _ in range(2)]

    def serve():
        while (message := worker_queue.get()) is not None:
            actor, index, operation = message
            job = jobs[index]
            event, released = job.perform(operation, policy, "AB"[index])
            status = "".join("1" if task.handle is not None else "0" for task in jobs)
            responses.put(f"step {actor} {index} {event} {status} {int(released)}")
        assert all(task.handle is None and task.terminal for task in jobs)
        responses.put("final " + " ".join(task.terminal for task in jobs))

    def forward(inbox):
        while (message := inbox.get()) is not None:
            worker_queue.put(message)

    worker = Thread(target=serve)
    clients = [Thread(target=forward, args=(inbox,)) for inbox in inboxes]
    worker.start()
    for client in clients:
        client.start()
    for line in sys.stdin:
        actor, slot, operation = line.split()
        inboxes[int(actor)].put((int(actor), int(slot), operation))
        print(responses.get(timeout=5))
    for inbox in inboxes:
        inbox.put(None)
    for client in clients:
        client.join()
    worker_queue.put(None)
    print(responses.get(timeout=5))
    worker.join()


if __name__ == "__main__":
    path, policy, mask = sys.argv[1:]
    run(Path(path), policy, int(mask))
