"""Python host implementation for calibrating the RT-01 CLI corpus."""

import operator
import os
import re
import sys


MIN_I64 = -(1 << 63)
MAX_I64 = (1 << 63) - 1
OPERATIONS = {b"+": operator.add, b"-": operator.sub, b"*": operator.mul}


def parse_i64(token):
    if not re.fullmatch(rb"[+-]?[0-9]+", token):
        raise ValueError
    magnitude = token.lstrip(b"+-").lstrip(b"0") or b"0"
    if len(magnitude) > 19:
        raise ValueError
    value = int(magnitude)
    if token.startswith(b"-"):
        value = -value
    if not MIN_I64 <= value <= MAX_I64:
        raise ValueError
    return value


def fail(message):
    sys.stderr.buffer.write(message + b"\n")
    return 1


def write(data):
    try:
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
    except BrokenPipeError:
        # Prevent a second flush failure when Python shuts down.
        with open(os.devnull, "wb") as sink:
            os.dup2(sink.fileno(), sys.stdout.fileno())
        return 1
    return 0


def calculate():
    record = sys.stdin.buffer.readline().strip(b" \t\r\n")
    parts = re.split(rb"[ \t\r]+", record)
    if len(parts) != 3:
        return fail(b"invalid input")
    left_token, operation, right_token = parts
    try:
        left, right = parse_i64(left_token), parse_i64(right_token)
    except ValueError:
        return fail(b"invalid input")
    if operation == b"/":
        if right == 0:
            return fail(b"division by zero")
        result = abs(left) // abs(right)
        if (left < 0) != (right < 0):
            result = -result
    elif operation in OPERATIONS:
        result = OPERATIONS[operation](left, right)
    else:
        return fail(b"invalid input")
    if not MIN_I64 <= result <= MAX_I64:
        return fail(b"arithmetic overflow")
    return write(f"{result}\n".encode("ascii"))


if __name__ == "__main__":
    program, *args = sys.argv[1:]
    if program == "hello":
        sys.exit(write(b"Hello, world!\n"))
    if program == "echo":
        sys.exit(write(b" ".join(map(os.fsencode, args)) + b"\n"))
    if program == "calculator":
        sys.exit(calculate())
    sys.exit(2)
