"""Check actual embedded CPython multi-interpreter ownership and teardown."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shlex
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
EXPECTED = ["value:104", "value:104", "callback-error", "value:206", "stale", "stale",
            "value:108", "value:209", "finalized"]


def run(args):
    return subprocess.check_output(args, text=True, timeout=30)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def check(config):
    prefix = Path(run([config, "--prefix"]).strip())
    includes = shlex.split(run([config, "--includes"]))
    libraries = shlex.split(run([config, "--embed", "--ldflags"]))
    libdir = next(Path(value[2:]) for value in libraries if value.startswith("-L"))
    python = next(libdir.glob("libpython3.*.so.1.0"))
    profiles = {}
    with TemporaryDirectory() as directory:
        binary = Path(directory) / "host"
        for level in ("-O0", "-O2"):
            run(["cc", "-std=c17", "-Wall", "-Wextra", "-Werror", level, *includes, HERE / "host.c",
                 *libraries, f"-Wl,-rpath,{libdir}", "-Wl,--build-id=none", "-o", binary])
            dependency = run(["readelf", "-dW", binary])
            assert f"Shared library: [{python.name}]" in dependency
            loader = run(["ldd", binary])
            assert str(python) in loader
            output = run([binary, prefix]).splitlines()
            assert output == EXPECTED * 2
            profiles[level] = {"archive_sha256": digest(binary), "trace": output, "cycles": 2}
    return {"native_cc": run(["cc", "--version"]).splitlines()[0],
            "python": run([prefix / "bin/python3", "--version"]).strip(), "libpython": python.name,
            "libpython_sha256": digest(python), "source_sha256": digest(HERE / "host.c"),
            "runner_sha256": digest(Path(__file__)), "profiles": profiles}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python-config", required=True)
    print(json.dumps(check(parser.parse_args().python_config), indent=2, sort_keys=True))
