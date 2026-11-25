"""Persist Lean artifacts and distinguish checking a new term from importing a module."""
import argparse
from contextlib import closing
from dataclasses import dataclass
from hashlib import file_digest, sha256
import json
import os
from pathlib import Path
import sqlite3
from subprocess import run
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
NAMESPACE = "CacheTrial"
CLEAN = "'CacheTrial.generated' does not depend on any axioms"
TAINTED = "'CacheTrial.generated' depends on axioms: [CacheTrial.environmentPremise]"
PROFILES = (
    ("base", None),
    ("comment", None),
    ("definitionally-equal", "n + (0 + 0)"),
    ("changed-meaning", "n + 1"),
)
SOURCE_CONTEXT = {"subject": "forall step n = n", "profile": "nat-definitional-equality/v1",
                  "assumptions": [], "review_policy": "no-axioms/v1"}
ARTIFACT_ROLES = {"dependency-source", "dependency-module", "proof-script", "proof-term", "proof-module"}


def digest(data):
    return sha256(data).hexdigest()


def hash_file(path):
    with path.open("rb") as source:
        return file_digest(source, "sha256").hexdigest()


@dataclass(frozen=True)
class Run:
    status: int
    output: str


def lean(tool, directory, *args):
    env = {"PATH": str(tool.parent) + os.pathsep + os.environ["PATH"],
           "LEAN_PATH": str(directory), "LC_ALL": "C"}
    result = run([str(tool), *args], cwd=directory, env=env, text=True, capture_output=True, timeout=12)
    return Run(result.returncode, (result.stdout + result.stderr).strip())


def success(result):
    assert result.status == 0, result.output
    return result.output


def extract(output):
    marker = f"theorem {NAMESPACE}.generated : {NAMESPACE}.Claim :=\n"
    assert output.startswith(marker) and output.endswith(CLEAN), output
    term = output.removeprefix(marker).removesuffix(CLEAN).strip()
    assert term.startswith("fun ") and "by" not in term.split()
    return term


def definition(base, profile, replacement):
    if profile == "comment":
        return base + "\n-- A source-only revision after all declarations.\n"
    return base if replacement is None else base.replace("n + 0", replacement)


def artifact_store(database, artifacts):
    with database.open("xb"):
        pass
    with closing(sqlite3.connect(database)) as store, store:
        store.execute("PRAGMA foreign_keys = ON")
        store.execute("CREATE TABLE cas (digest TEXT PRIMARY KEY, body BLOB NOT NULL)")
        store.execute("CREATE TABLE roles (role TEXT PRIMARY KEY, digest TEXT NOT NULL REFERENCES cas)")
        for role, body in artifacts.items():
            address = digest(body)
            store.execute("INSERT OR IGNORE INTO cas VALUES (?, ?)", (address, body))
            store.execute("INSERT INTO roles VALUES (?, ?)", (role, address))


def load(database):
    with closing(sqlite3.connect(database)) as store:
        result = {}
        for role, address, payload in store.execute("SELECT role, roles.digest, body FROM roles JOIN cas USING(digest)"):
            if digest(payload) != address:
                raise ValueError(f"corrupt artifact in {role}")
            result[role] = payload
        if result.keys() != ARTIFACT_ROLES:
            raise ValueError("incomplete artifact inventory")
        return result


def proof_source(name, term):
    return f"import Defs\n\nnamespace CacheTrial\n\ntheorem {name} : Claim :=\n  {term}\n\nend CacheTrial\n\n#print axioms CacheTrial.{name}\n"


def write(directory, filename, text):
    (directory / filename).write_text(text)


def status(output, theorem):
    if output.status:
        assert "error" in output.output, output
        return "refused"
    assert f"'{theorem}' does not depend on any axioms" in output.output, output
    return "checked"


def exact_module_reuse(tool, directory, expected):
    inputs = {"dependency-source": "Defs.lean", "dependency-module": "Defs.olean",
              "proof-module": "Synth.olean"}
    for role, filename in inputs.items():
        path = directory / filename
        if not path.is_file() or path.read_bytes() != expected[role]:
            return "refused-before-import"
    return status(lean(tool, directory, "Consume.lean"), "admitted")


def native_controls(tool, directory, synth, consume):
    controls = {}
    for label, new_theorem, expected in (
        ("wrong-theorem", "theorem generated : True := True.intro", "refused"),
        ("declared-axiom", "axiom environmentPremise : Claim\ntheorem generated : Claim := environmentPremise", "axiom-policy"),
    ):
        source = synth.split("theorem generated", 1)[0] + new_theorem + "\nend CacheTrial\n"
        write(directory, "Synth.lean", source)
        success(lean(tool, directory, "-o", "Synth.olean", "Synth.lean"))
        write(directory, "Consume.lean", consume)
        checked = lean(tool, directory, "Consume.lean")
        if expected == "refused":
            assert checked.status != 0 and "type mismatch" in checked.output.lower(), checked
        else:
            assert checked.status == 0 and TAINTED in checked.output, checked
        controls[label] = expected
    return controls


def exercise(tool, directory):
    base = (HERE / "Defs.lean").read_text()
    synth = (HERE / "Synth.lean").read_text()
    consume = (HERE / "Consume.lean").read_text()
    write(directory, "Defs.lean", base)
    write(directory, "Synth.lean", synth)
    success(lean(tool, directory, "-o", "Defs.olean", "Defs.lean"))
    term = extract(success(lean(tool, directory, "-o", "Synth.olean", "Synth.lean")))
    source_term = proof_source("replayed", term)
    artifacts = {
        "dependency-source": base.encode(),
        "dependency-module": (directory / "Defs.olean").read_bytes(),
        "proof-script": synth.encode(),
        "proof-term": source_term.encode(),
        "proof-module": (directory / "Synth.olean").read_bytes(),
    }
    database = directory / "proof-cache.sqlite"
    artifact_store(database, artifacts)
    archived = load(database)
    assert archived == artifacts
    write(directory, "Consume.lean", consume)
    write(directory, "Term.lean", archived["proof-term"].decode())
    write(directory, "Fresh.lean", proof_source("fresh", "by exact fun n => rfl"))
    (directory / "Synth.olean").unlink()
    (directory / "Synth.olean").write_bytes(archived["proof-module"])
    observations = {}
    for label, replacement in PROFILES:
        source = definition(base, label, replacement)
        write(directory, "Defs.lean", source)
        success(lean(tool, directory, "-o", "Defs.olean", "Defs.lean"))
        imported = (directory / "Defs.olean").read_bytes()
        source_pin = source.encode() == archived["dependency-source"]
        module_pin = imported == archived["dependency-module"]
        assert source_pin == (label == "base")
        if label == "base":
            assert module_pin
        else:
            assert not (source_pin and module_pin)
        from_term = status(lean(tool, directory, "Term.lean"), "CacheTrial.replayed")
        from_script = status(lean(tool, directory, "Synth.lean"), "CacheTrial.generated")
        from_fresh = status(lean(tool, directory, "Fresh.lean"), "CacheTrial.fresh")
        cached = status(lean(tool, directory, "Consume.lean"), "admitted")
        zero_trust = status(lean(tool, directory, "-t0", "Consume.lean"), "admitted")
        verified_import = exact_module_reuse(tool, directory, archived)
        assert cached == zero_trust == "checked"
        assert verified_import == ("checked" if label == "base" else "refused-before-import")
        expected = "refused" if label == "changed-meaning" else "checked"
        assert from_term == from_script == from_fresh == expected
        observations[label] = {
            "dependency_source": digest(source.encode()), "dependency_module": digest(imported),
            "stored_term": from_term, "replayed_tactic": from_script, "fresh_generation": from_fresh,
            "ordinary_import": cached, "import_with_t0": zero_trust,
            "exact_artifact_reuse": verified_import,
        }

    write(directory, "Defs.lean", base)
    success(lean(tool, directory, "-o", "Defs.olean", "Defs.lean"))
    controls = native_controls(tool, directory, synth, consume)
    (directory / "Defs.olean").unlink()
    missing = lean(tool, directory, "Consume.lean")
    assert missing.status != 0, missing
    controls["absent-module"] = "refused"
    with closing(sqlite3.connect(database)) as store, store:
        store.execute("UPDATE cas SET body = ? WHERE digest = ?", (b"damaged", digest(artifacts["proof-module"])))
    try:
        load(database)
    except ValueError as error:
        assert str(error) == "corrupt artifact in proof-module"
    else:
        raise AssertionError("corrupt payload accepted")
    controls["damaged-stored-payload"] = "refused-before-import"
    unavailable_database = directory / "incomplete.sqlite"
    artifact_store(unavailable_database, {role: body for role, body in artifacts.items() if role != "proof-term"})
    try:
        load(unavailable_database)
    except ValueError as error:
        assert str(error) == "incomplete artifact inventory"
    else:
        raise AssertionError("incomplete inventory accepted")
    controls["missing-stored-role"] = "refused-before-import"
    return artifacts, {"term": term, "semantic_scope": SOURCE_CONTEXT, "cases": observations, "controls": controls,
            "stored_lean_artifacts": {role: {"bytes": len(body), "sha256": digest(body)}
                                      for role, body in artifacts.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--archive", type=Path, help="Write the five checked artifact roles to a new SQLite database.")
    args = parser.parse_args()
    tool = args.lean.resolve(strict=True)
    with TemporaryDirectory() as temporary:
        directory = Path(temporary)
        version = success(lean(tool, directory, "--version"))
        assert "version 4.36.0" in version and "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9" in version
        prefix = Path(success(lean(tool, directory, "--print-prefix")))
        exact = {name: hash_file(prefix / name) for name in ("bin/lean", "lib/lean/libleanshared.so", "lib/lean/Init.olean")}
        artifacts, evidence = exercise(tool, directory)
    if args.archive:
        artifact_store(args.archive, artifacts)
        assert load(args.archive) == artifacts
    args.output.write_text(json.dumps({"lean": version, "tool_hashes": exact, "sqlite": sqlite3.sqlite_version,
                                      "experiment": evidence}, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
