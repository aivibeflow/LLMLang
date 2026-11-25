"""Check C ABI allocator selection, exclusive borrow, settlement and typed failures."""

import errno
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
OBSERVATIONS = ["wrong-provider:2", "oversize:1", "aliased-borrow:4", "cancel:0",
                "release-pending:4", "settle:0", "stale-borrow:3", "settled-byte:5", "release:0",
                "retired-generation:3", "new-byte:0"]


def run(args):
    return subprocess.check_output(args, text=True, timeout=20)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def check():
    options = ["cc", "-std=c17", "-Wall", "-Wextra", "-Werror", "-Wl,--build-id=none"]
    rows = {}
    with TemporaryDirectory() as directory:
        folder = Path(directory)
        library = folder / "liblease.so"
        client = folder / "client"
        for level in ("-O0", "-O2"):
            run([*options, level, "-fPIC", "-shared", HERE / "provider.c", "-o", library])
            run([*options, level, HERE / "client.c", f"-L{folder}", "-llease", "-Wl,-rpath,$ORIGIN", "-o", client])
            ld = run(["readelf", "-dW", client])
            assert "Shared library: [liblease.so]" in ld and "[$ORIGIN]" in ld
            actual = run([client]).splitlines()
            expected = [*OBSERVATIONS, f"backend-error:{errno.ENOMEM}", *OBSERVATIONS,
                        f"backend-error:{errno.EINVAL}"]
            assert actual == expected
            rows[level] = {"provider_sha256": digest(library), "client_sha256": digest(client), "trace": actual}
    return {"compiler": run(["cc", "--version"]).splitlines()[0],
            "libc": run(["getconf", "GNU_LIBC_VERSION"]).strip(),
            "sources": {name: digest(HERE / name) for name in ("client.c", "provider.c", "provider.h", "check.py")},
            "profiles": rows}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, sort_keys=True))
