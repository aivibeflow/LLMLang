"""Check offline source-line resolution for exact native debug sessions."""

import argparse
from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
import re
import subprocess
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
BASE = """__attribute__((noinline)) int helper(int value) {
    return value + 1;
}
int main(void) { return helper(2) == 3 ? 0 : 1; }
"""
MOVED = BASE.replace("    return value", "    /* documented boundary */\n\n    return value")
ROWS = re.compile(r"^probe\.c\s+(\d+)\s+(0x[0-9a-f]+)")


def execute(args, cwd):
    return subprocess.run(args, cwd=cwd, check=True, text=True,
                          capture_output=True, timeout=30).stdout


def digest(data):
    return sha256(data).hexdigest()


def bind(session, request):
    if any(session[field] != request[field] for field in ("artifact", "source", "target", "profile")):
        return "context-mismatch", []
    addresses = session["rows"].get(request["line"], [])
    return ("resolved" if addresses else "unavailable"), addresses


def compile_profile(args, work, revision, optimization, debug):
    seed = work / f"{revision}-{optimization[2:]}-{debug}"
    seed.mkdir()
    code = BASE if revision == "base" else MOVED
    source = seed / "probe.c"
    source.write_text(code)
    binary = seed / "probe"
    flags = ["-gdwarf-4", f"-fdebug-prefix-map={seed}=/fixture"] if debug else ["-g0", "-s"]
    execute([args.cc, "-std=c11", "-Wall", "-Wextra", "-Werror", "-no-pie", optimization,
             *flags, "probe.c", "-o", binary], seed)
    execute([binary], seed)
    rows = {}
    for line in execute([args.readelf, "--debug-dump=decodedline", binary], seed).splitlines():
        match = ROWS.match(line.strip())
        if match:
            position, pc = int(match[1]), match[2]
            addresses = rows.setdefault(position, [])
            if pc not in addresses:
                addresses.append(pc)
    assert bool(rows) is debug
    symbols = {}
    if debug:
        for raw in execute([args.readelf, "--symbols", binary], seed).splitlines():
            columns = raw.split()
            if len(columns) >= 8 and columns[3] == "FUNC" and columns[-1] in ("main", "helper"):
                symbols[columns[-1]] = (int(columns[1], 16), int(columns[2]))
        assert set(symbols) == {"main", "helper"}
    line = next(n for n, text in enumerate(code.splitlines(), 1) if "return value + 1;" in text)
    return {"artifact": digest(binary.read_bytes()), "source": digest(code.encode()),
            "target": platform.machine(), "profile": f"{optimization}/{'dwarf4' if debug else 'stripped'}",
            "requested_line": line, "rows": rows, "symbols": symbols}


def measure(args, work):
    sessions = {}
    for revision, level, debug in product(("base", "moved"), ("-O0", "-O2"), (False, True)):
        session = compile_profile(args, work, revision, level, debug)
        sessions[f"{revision}/{session['profile']}"] = session

    comparisons = Counter()
    for from_session, to_session in product(sessions.values(), repeat=2):
        query = {**{field: to_session[field] for field in ("artifact", "source", "target", "profile")},
                 "line": to_session["requested_line"]}
        status, addresses = bind(from_session, query)
        same_context = (from_session["profile"], from_session["source"]) == (
            to_session["profile"], to_session["source"])
        expected = ("context-mismatch" if not same_context else
                    "resolved" if "dwarf4" in from_session["profile"] else "unavailable")
        assert status == expected and bool(addresses) == (expected == "resolved"), (query, from_session)
        comparisons[status] += 1

    base = sessions["base/-O0/dwarf4"]
    moved = sessions["moved/-O0/dwarf4"]
    stale_line = moved["requested_line"]
    assert stale_line != base["requested_line"] and base["rows"][stale_line]
    assert base["rows"][stale_line] != base["rows"][base["requested_line"]]
    main, size = base["symbols"]["main"]
    assert any(main <= int(pc, 16) < main + size for pc in base["rows"][stale_line])
    wrong_target = {**base, "target": "fixture:other-target", "line": base["requested_line"]}
    assert bind(base, wrong_target) == ("context-mismatch", [])
    assert sessions["base/-O0/stripped"]["artifact"] == sessions["moved/-O0/stripped"]["artifact"]
    return {"python": platform.python_version(), "compiler": execute([args.cc, "--version"], work).splitlines()[0],
            "readelf": execute([args.readelf, "--version"], work).splitlines()[0],
            "profiles": sessions, "comparisons": comparisons,
            "old_artifact_has_rows_for_moved_line": base["rows"][stale_line],
            "old_line_includes_main_symbol": True, "wrong_target": "context-mismatch",
            "source_sha256": digest(Path(__file__).read_bytes())}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", required=True)
    parser.add_argument("--readelf", required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="rt17-debug-source-") as work:
        print(json.dumps(measure(args, Path(work)), sort_keys=True, indent=2))
