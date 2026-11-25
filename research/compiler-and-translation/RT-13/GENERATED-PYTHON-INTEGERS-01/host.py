"""Execute a generated module against the existing binary observation protocol."""

import hashlib
import json
import marshal
from pathlib import Path
import struct
import sys


SENTINEL = 0xabad1234


def main():
    code = compile(Path(sys.argv[1]).read_bytes(), "generated_probe.py", "exec",
                   dont_inherit=True)
    namespace = {}
    exec(code, namespace)
    entries = namespace["ENTRIES"]
    request = sys.stdin.buffer.read()
    response = bytearray()
    for index, a, b, enabled in struct.iter_unpack("<4I", request):
        events = []
        slot = [SENTINEL]
        status = entries[index](a, b, enabled, events.append, slot)
        count = len(events)
        if count not in (1, 2):
            raise ValueError(f"Unexpected event count: {count}")
        first = events[0]
        second = events[1] if count == 2 else 0
        response.extend(struct.pack("<5I", status, slot[0], count, first, second))
    sys.stdout.buffer.write(response)
    print(json.dumps({"bytecode_sha256": hashlib.sha256(marshal.dumps(code)).hexdigest(),
                      "optimization": sys.flags.optimize,
                      "entries": len(entries)}), file=sys.stderr)


if __name__ == "__main__":
    main()
