"""Persist source-bound cvc5 certificates and independently check CPC and Alethe."""
import argparse
from contextlib import closing
from dataclasses import asdict, dataclass, replace
from hashlib import file_digest, sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import sqlite3
from subprocess import check_output, run
import tarfile
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PROTOTYPE = Path("research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding")
PIN = "481f748eed2ef3ba9057b014c8bc8706b9b846db"
LOGOS = "cf18742973861b3718d04c5f25775448098ff474"
FORMATS = ("cpc", "alethe")
POLICY = "closed-qf-lia-certificate/v1"


def fingerprint(data):
    return sha256(data).hexdigest()


def content(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def tool_digest(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


@dataclass(frozen=True)
class Subject:
    revision: str
    required: int
    excluded: int


def render(subject):
    return (
        f"(set-logic QF_LIA)\n(declare-const x Int)\n(assert (= x {subject.required}))\n"
        f"(assert (not (= x {subject.excluded})))\n(check-sat)\n(exit)\n"
    ).encode()


def invoke(command, directory, env):
    return run(command, cwd=directory, env=env, capture_output=True, timeout=30)


def complete(process):
    assert process.returncode == 0, (process.returncode, process.stderr, process.stdout)
    return process.stdout


def compile_scope(tool, directory, logos_library, base_env):
    archive = check_output(["git", "archive", PIN, PROTOTYPE.as_posix()], cwd=ROOT)
    with tarfile.open(fileobj=BytesIO(archive)) as saved:
        saved.extractall(directory, filter="data")
    build = directory / PROTOTYPE
    env = {**base_env, "LEAN_PATH": os.pathsep.join(map(str, (build, logos_library)))}
    pins = {}

    def compile_one(module):
        source = build / f"{module}.lean"
        if not source.is_file() or module in pins:
            return
        text = source.read_text()
        for dependency in re.findall(r"^import ([\w.]+)$", text, re.M):
            compile_one(dependency)
        complete(invoke([tool, "-o", f"{module}.olean", source.name], build, env))
        pins[module] = fingerprint(text.encode())

    compile_one("CpcNullaryAliases")
    return env, pins


def generate(tool, format_name, query, directory, env):
    src = directory / "Query.smt2"
    src.write_bytes(query)
    flags = ["--produce-proofs", f"--proof-format-mode={format_name}", "--dump-proofs"]
    if format_name == "alethe":
        flags.append("--proof-alethe-res-pivots")
    raw = complete(invoke([tool, *flags, src], directory, env))
    disposition = raw.splitlines()[0].decode()
    assert disposition in ("sat", "unsat"), raw
    return disposition, raw


def assess(tools, format_name, query, raw, directory, env):
    src = directory / "Current.smt2"
    src.write_bytes(query)
    if format_name == "cpc":
        proof = directory / "Certificate.cpc.raw"
        proof.write_bytes(raw)
        return complete(invoke([tools.lean, "--run", HERE / "CpcReplay.lean", src, proof],
                               directory, env)).decode().strip()
    lines = raw.splitlines()
    if len(lines) < 4 or lines[:2] != [b"unsat", b"("] or lines[-1] != b")":
        return "missing-alethe-certificate"
    proof = directory / "Certificate.alethe"
    proof.write_bytes(b"\n".join(lines[2:-1]) + b"\n")
    check = invoke([tools.carcara, "check", proof, src], directory, env)
    disposition = check.stdout.decode().strip().splitlines()
    if check.returncode == 0 and disposition == ["valid"]:
        return "checked"
    if disposition == ["holey"]:
        return "holey"
    return "refused"


def request(subject, query, format_name, pins):
    return fingerprint(content({
        "source": fingerprint(content(asdict(subject))), "query": fingerprint(query),
        "format": format_name, "policy": POLICY, "tool_subject": pins[format_name],
    }))


def save(store, subject, query, format_name, raw, pins):
    identity = request(subject, query, format_name, pins)
    encoded_subject = content(asdict(subject))
    with store:
        for payload in (encoded_subject, query, raw):
            store.execute("INSERT OR IGNORE INTO cas VALUES (?, ?)", (fingerprint(payload), payload))
        store.execute("INSERT INTO receipts VALUES (?, ?, ?, ?)",
                      (identity, fingerprint(encoded_subject), fingerprint(query), fingerprint(raw)))
    return identity


def lookup(store, subject, query, format_name, pins):
    key = request(subject, query, format_name, pins)
    row = store.execute("SELECT source, query, proof FROM receipts WHERE id = ?", (key,)).fetchone()
    if row is None:
        return "miss", None
    parts = []
    for address in row:
        stored = store.execute("SELECT data FROM cas WHERE hash = ?", (address,)).fetchone()
        if stored is None or fingerprint(stored[0]) != address:
            return "damaged", None
        parts.append(stored[0])
    if parts[:2] != [content(asdict(subject)), query]:
        return "wrong-subject", None
    return "hit", parts[2]


def z3_check(path, query, directory, env):
    script = directory / "Z3.smt2"
    script.write_bytes(query)
    return complete(invoke([path, "-smt2", script], directory, env)).decode().strip()


def assess_matrix(tools, root, env, pins):
    base = Subject("source-v1", 3, 3)
    scopes = {
        "original": base,
        "metadata-only": replace(base, revision="source-v2"),
        "different-unsat": Subject("source-v3", 7, 7),
        "different-sat": Subject("source-v4", 3, 7),
    }
    database = root / "proofs.sqlite"
    with closing(sqlite3.connect(database)) as store:
        store.execute("PRAGMA foreign_keys = ON")
        store.execute("CREATE TABLE cas (hash TEXT PRIMARY KEY, data BLOB NOT NULL)")
        store.execute("""CREATE TABLE receipts (
            id TEXT PRIMARY KEY, source TEXT NOT NULL REFERENCES cas(hash),
            query TEXT NOT NULL REFERENCES cas(hash), proof TEXT NOT NULL REFERENCES cas(hash))""")
        initial = {}
        for kind in FORMATS:
            query = render(base)
            expected, raw = generate(tools.cvc5, kind, query, root, env)
            assert expected == "unsat" and assess(tools, kind, query, raw, root, env) == "checked"
            initial[kind] = save(store, base, query, kind, raw, pins)

    rows = {}
    with closing(sqlite3.connect(database)) as store:
        store.execute("PRAGMA foreign_keys = ON")
        old = {}
        for kind in FORMATS:
            hit, saved = lookup(store, base, render(base), kind, pins)
            assert hit == "hit"
            old[kind] = saved

        for label, subject in scopes.items():
            query = render(subject)
            expected = "sat" if subject.required != subject.excluded else "unsat"
            assert z3_check(tools.z3, query, root, env) == expected
            corpus_row = {"source": asdict(subject), "source_digest": fingerprint(content(asdict(subject))),
                          "query_sha256": fingerprint(query), "z3_verdict": expected, "formats": {}}
            if expected == "sat":
                model_query = query.replace(b"(exit)", b"(get-value (x))\n(exit)")
                model = z3_check(tools.z3, model_query, root, env)
                values = re.fullmatch(r"sat\s+\(\(x ([0-9]+)\)\)", model)
                assert values and int(values[1]) == subject.required and int(values[1]) != subject.excluded
                corpus_row["independently_checked_model"] = int(values[1])
            for kind in FORMATS:
                hit, value = lookup(store, subject, query, kind, pins)
                assert hit == ("hit" if label == "original" else "miss")
                if hit == "hit":
                    assert value == old[kind]
                cached = assess(tools, kind, query, old[kind], root, env)
                assert (cached == "checked") == (label in {"original", "metadata-only"}), (label, kind, cached)
                generated, raw = generate(tools.cvc5, kind, query, root, env)
                assert generated == expected
                fresh = assess(tools, kind, query, raw, root, env)
                assert (fresh == "checked") == (expected == "unsat"), (label, kind, fresh)
                if label in {"original", "metadata-only"}:
                    assert raw == old[kind]
                corpus_row["formats"][kind] = {
                    "exact_lookup": hit, "recheck_old": cached, "generated_verdict": generated,
                    "fresh_check": fresh, "fresh_raw": raw.decode(),
                }
                if label in {"metadata-only", "different-unsat"}:
                    identity = save(store, subject, query, kind, old[kind] if label == "metadata-only" else raw, pins)
                    assert identity != initial[kind]
                    hit, _ = lookup(store, subject, query, kind, pins)
                    assert hit == "hit"
                    corpus_row["formats"][kind]["new_receipt"] = identity
                    if label == "different-unsat":
                        assert raw != old[kind]
            rows[label] = corpus_row

        controls = {}
        for kind in FORMATS:
            query = render(base)
            broken = old[kind].replace(b":rule contra" if kind == "cpc" else b":rule resolution",
                                       b":rule unknown_fixture_rule", 1)
            assert broken != old[kind]
            outcome = assess(tools, kind, query, broken, root, env)
            assert outcome != "checked"
            controls[f"{kind}-invalid-rule"] = outcome
            verdict_only = assess(tools, kind, query, b"unsat\n", root, env)
            assert "missing-" in verdict_only
            controls[f"{kind}-verdict-without-proof"] = verdict_only
            foreign_tools = {**pins, kind: "different-checker"}
            assert lookup(store, base, query, kind, foreign_tools) == ("miss", None)
            controls[f"{kind}-changed-checker"] = "miss"
        holey = old["alethe"].replace(b":rule resolution :premises (a0 a1) :args (@p_1 true)",
                                      b":rule hole", 1)
        assert holey != old["alethe"]
        controls["alethe-with-hole"] = assess(tools, "alethe", render(base), holey, root, env)
        assert controls["alethe-with-hole"] == "holey"
        with store:
            store.execute("UPDATE cas SET data = ? WHERE hash = ?",
                          (b"incomplete bytes", fingerprint(old["cpc"])))
        assert lookup(store, base, render(base), "cpc", pins) == ("damaged", None)
        assert lookup(store, base, render(base), "alethe", pins) == ("hit", old["alethe"])
        controls["damaged-cache-payload"] = "damaged"
        return {"scopes": rows, "initial_receipts": initial, "controls": controls,
                "actual_stored_receipts": store.execute("SELECT COUNT(*) FROM receipts").fetchone()[0]}


def check(tools, directory):
    logos = tools.logos.resolve()
    assert check_output(["git", "-C", logos, "rev-parse", "HEAD"], text=True).strip() == LOGOS
    assert not check_output(["git", "-C", logos, "status", "--porcelain", "--untracked-files=no"])
    lib = logos / ".lake/build/lib/lean"
    environment = {**os.environ, "LC_ALL": "C"}
    env, source_pins = compile_scope(tools.lean, directory, lib, environment)
    binaries = {key: tool_digest(getattr(tools, key)) for key in ("lean", "cvc5", "carcara", "z3")}
    versions = {key: complete(invoke([getattr(tools, key), "--version"], directory, env)).decode().splitlines()[0]
                for key in binaries}
    assert "4.36.0" in versions["lean"] and "1.4.2" in versions["cvc5"]
    assert "1.1.0" in versions["carcara"] and "4.13.3" in versions["z3"]
    runtime = {path.relative_to(lib).as_posix(): tool_digest(path)
               for path in sorted(lib.rglob("*.olean"))}
    assert "Cpc/Api.olean" in runtime
    lean_shared = tool_digest(tools.lean.parent.parent / "lib/lean/libleanshared.so")
    pins = {
        "cpc": fingerprint(content([binaries["cvc5"], binaries["lean"], lean_shared, runtime, source_pins,
                                    fingerprint((HERE / "CpcReplay.lean").read_bytes())])),
        "alethe": fingerprint(content([binaries["cvc5"], binaries["carcara"], "proof-alethe-res-pivots"])),
    }
    evidence = assess_matrix(tools, directory, env, pins)
    return {"source_revision": PIN, "logos_revision": LOGOS, "logos_modules": runtime,
            "lean_shared": lean_shared, "sqlite": sqlite3.sqlite_version,
            "tool_versions": versions, "tool_hashes": binaries,
            "binding_sources": source_pins, **evidence}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for tool in ("lean", "cvc5", "carcara", "z3", "logos", "output"):
        parser.add_argument("--" + tool, required=True, type=Path)
    args = parser.parse_args()
    for tool in ("lean", "cvc5", "carcara", "z3"):
        setattr(args, tool, getattr(args, tool).resolve(strict=True))
    with TemporaryDirectory() as work:
        result = check(args, Path(work))
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
