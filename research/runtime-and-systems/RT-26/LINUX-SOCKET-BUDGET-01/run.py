"""Compare delivered payload, socket consumption and budget admission on Linux loopback."""

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import sys


TARGET = ("127.0.0.1", 0)
PAYLOAD = b"abcdefghijklmnop"
SHORT = b"abcd"
LIMIT = 4
TIMEOUT = 5


@contextmanager
def udp():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender, socket.socket(
        socket.AF_INET, socket.SOCK_DGRAM,
    ) as receiver:
        receiver.bind(TARGET)
        receiver.settimeout(TIMEOUT)
        sender.connect(receiver.getsockname())
        yield sender, receiver


def send(sender, data):
    sent = sender.send(data)
    if sent != len(data):
        raise AssertionError((sent, len(data)))
    return sent


def receive(receiver, capacity, flags=0):
    output = bytearray(capacity)
    size, _, result, _ = receiver.recvmsg_into([output], 0, flags)
    copied = bytes(output[:min(size, capacity)])
    return {"reported_bytes": size, "copied": copied.decode("ascii"),
            "truncated": bool(result & socket.MSG_TRUNC)}


def peek(receiver):
    return receive(receiver, 1, socket.MSG_PEEK | socket.MSG_TRUNC)["reported_bytes"]


def empty_datagram_queue(receiver):
    timeout = receiver.gettimeout()
    receiver.setblocking(False)
    try:
        receiver.recv(1)
    except BlockingIOError:
        return True
    finally:
        receiver.settimeout(timeout)
    return False


def udp_truncation(native_length):
    with udp() as (sender, receiver):
        sent = send(sender, PAYLOAD)
        observed = receive(receiver, LIMIT, socket.MSG_TRUNC if native_length else 0)
        drained = empty_datagram_queue(receiver)
        wanted = {"reported_bytes": len(PAYLOAD) if native_length else LIMIT,
                  "copied": SHORT.decode(), "truncated": True}
        if observed != wanted or not drained:
            raise AssertionError((observed, wanted, drained))
        return {"sent": sent, "receive": observed, "queue_drained": drained,
                "application_bytes": LIMIT, "removed_datagram_bytes": len(PAYLOAD)}


def stream():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener, socket.socket(
        socket.AF_INET, socket.SOCK_STREAM,
    ) as sender:
        listener.bind(TARGET)
        listener.listen(1)
        listener.settimeout(TIMEOUT)
        sender.settimeout(TIMEOUT)
        sender.connect(listener.getsockname())
        receiver, _ = listener.accept()
        with receiver:
            receiver.settimeout(TIMEOUT)
            sent = send(sender, PAYLOAD)
            sender.shutdown(socket.SHUT_WR)
            prefix = receiver.recv(LIMIT, socket.MSG_WAITALL)
            tail = receiver.recv(len(PAYLOAD) - LIMIT, socket.MSG_WAITALL)
            eof = receiver.recv(1)
            if (prefix, tail, eof) != (SHORT, PAYLOAD[LIMIT:], b""):
                raise AssertionError((prefix, tail, eof))
            return {"sent": sent, "first_read": prefix.decode(), "application_bytes": len(prefix),
                    "remaining_bytes": len(tail), "remaining_contents": tail.decode(), "eventual_eof": True}


def strict_budget():
    with udp() as (sender, receiver):
        sent = send(sender, PAYLOAD)
        length = peek(receiver)
        allowed = length <= LIMIT
        remains = peek(receiver)
        if (length, allowed, remains) != (len(PAYLOAD), False, len(PAYLOAD)):
            raise AssertionError((length, allowed, remains))
        recovered = receive(receiver, len(PAYLOAD), socket.MSG_TRUNC)
        if recovered["copied"] != PAYLOAD.decode() or not empty_datagram_queue(receiver):
            raise AssertionError("A refused datagram must remain fully queued")
        return {"sent": sent, "budget": LIMIT, "peeked": length, "admitted": allowed,
                "uncharged_pending_bytes": remains, "later_full_receive": recovered}


def intervening_consumer():
    with udp() as (sender, receiver):
        send(sender, SHORT)
        send(sender, PAYLOAD)
        # Two invocation endpoints share the same Linux socket receive queue.
        with socket.socket(fileno=os.dup(receiver.fileno())) as second:
            second.settimeout(TIMEOUT)
            initial = peek(receiver)
            competing = receive(second, LIMIT, socket.MSG_TRUNC)
            admitted = initial <= LIMIT
            if not admitted:
                raise AssertionError("The first small datagram should pass the peek policy")
            actual = receive(receiver, LIMIT, socket.MSG_TRUNC)
        if competing["copied"] != SHORT.decode() or competing["truncated"]:
            raise AssertionError(("competing consumer", competing))
        if actual["reported_bytes"] != len(PAYLOAD) or not actual["truncated"] or not empty_datagram_queue(receiver):
            raise AssertionError(("stale size admission must admit excess dequeue", actual))
        return {"budget": LIMIT, "first_peeked": initial, "first_admitted": admitted,
                "competing_receive": competing, "actual_receive": actual,
                "original_invocation_dequeued_bytes": actual["reported_bytes"]}


def verify():
    return {"format": "rt26-linux-socket-budget/1", "python": sys.version.split()[0],
            "kernel_release": os.uname().release, "machine": os.uname().machine,
            "cases": {
                "tcp_split_read": stream(), "udp_truncated": udp_truncation(False),
                "udp_report_full_length": udp_truncation(True),
                "udp_peek_then_refuse": strict_budget(),
                "udp_competing_receive": intervening_consumer(),
            }}


if __name__ == "__main__":
    if sys.platform != "linux":
        raise SystemExit("this fixture uses Linux recvmsg length semantics")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    opts = parser.parse_args()
    opts.output.write_text(json.dumps(verify(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
