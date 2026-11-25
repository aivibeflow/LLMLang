"""Check versioned Go loop capture using actual native pipe descriptors."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory


MODES = ("declared-loop-capture", "assigned-loop-capture", "snapshot-capture", "direct-argument")


def expected(language, mode, count):
    reused = mode == "assigned-loop-capture" or (mode == "declared-loop-capture" and language == "go1.21")
    selections = [count] * count if reused else list(range(count, 0, -1))
    closed = set()
    events = []
    for address in selections:
        events.append({"id": address, "status": "already-closed" if address in closed else "closed"})
        closed.add(address)
    return {
        "mode": mode, "count": count, "closes": events,
        "live_after_scope": [address for address in range(1, count + 1) if address not in closed],
    }


def study(options):
    source = Path(__file__).with_name("main.go")
    environment = os.environ | {
        "GOCACHE": str(options.cache.resolve()), "GOENV": "off", "GOWORK": "off", "GOTOOLCHAIN": "local",
        "GOPROXY": "off", "GOSUMDB": "off", "CGO_ENABLED": "0", "GOFLAGS": "",
    }
    profiles = {}
    with TemporaryDirectory() as temporary:
        for language in ("go1.21", "go1.22"):
            program = Path(temporary) / f"fixture-{language}"
            flag = f"-gcflags=-lang={language}"
            subprocess.run(
                [options.go, "build", "-trimpath", "-buildvcs=false", flag, "-o", str(program), str(source)],
                env=environment, check=True, timeout=60,
            )
            metadata = subprocess.check_output([options.go, "version", "-m", program], env=environment,
                                               text=True, timeout=10)
            assert flag in metadata, metadata
            output = subprocess.check_output([program], text=True, timeout=10)
            cases = [json.loads(line) for line in output.splitlines()]
            assert cases == [expected(language, mode, count) for mode in MODES for count in range(5)]
            profiles[language] = {
                "binary_sha256": hashlib.sha256(program.read_bytes()).hexdigest(),
                "cases": cases,
                "cases_with_live_descriptors": sum(bool(case["live_after_scope"]) for case in cases),
            }
    assert profiles["go1.21"]["cases_with_live_descriptors"] == 6
    assert profiles["go1.22"]["cases_with_live_descriptors"] == 3
    return {
        "go": subprocess.check_output([options.go, "version"], env=environment, text=True).strip(),
        "python": platform.python_version(), "profiles": profiles,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--go", default="go")
    parser.add_argument("--cache", type=Path, required=True)
    print(json.dumps(study(parser.parse_args()), indent=2, sort_keys=True))
