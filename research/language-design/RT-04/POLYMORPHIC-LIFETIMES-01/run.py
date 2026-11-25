#!/usr/bin/env python3
"""Check universal lifetime, dynamic interfaces, and typed Rust client behavior."""

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
CASES = {
    "higher-ranked-function": (
        """let chooser: ScopedSelector = select_left;
           for n in -32..32 {
               let left = n;
               let right = 2 * n;
               println!("{}", through(chooser, &left, &right));
           }""",
        list(range(-32, 32)),
    ),
    "static-provider-under-polymorphic-signature": (
        """let chooser: ScopedSelector = select_static;
           for n in 0..64 {
               let local = n;
               println!("{}", through(chooser, &local, &local));
           }""",
        [7000] * 64,
    ),
    "static-only-instantiation": (
        """static INITIAL: i32 = 11;
           for _ in 0..64 { println!("{}", static_only(&INITIAL, &INITIAL)); }""",
        [11] * 64,
    ),
    "erased-lifetime-indexed-method": (
        """let choices: [&dyn ScopedLookup; 2] = [&Right, &Static];
           for n in -32..32 {
               let left = n;
               let right = n * 3;
               for choice in choices { println!("{}", choice.select(&left, &right)); }
           }""",
        [value for n in range(-32, 32) for value in (3 * n, 7000)],
    ),
    "explicit-associated-type": (
        """let erased: &dyn Associated<Item = u16> = &Right;
           for _ in 0..64 { println!("{}", erased.item()); }""",
        [17] * 64,
    ),
    "concrete-type-parameter": (
        """for n in 0..64 {
               let wide = Right.identity(n as u64);
               let narrow = Right.identity(n as u16);
               println!("{}", wide + u64::from(narrow));
           }""",
        [2 * n for n in range(64)],
    ),
    "sized-only-generic-with-erased-label": (
        """let erased: &dyn SizedGeneric = &Right;
           for n in 0..64 {
               println!("{}", erased.label() + Right.map(n));
           }""",
        [19 + n for n in range(64)],
    ),
    "static-only-is-not-higher-ranked": (
        """let chooser: ScopedSelector = static_only;
           println!("{}", through(chooser, &12, &13));""",
        "E0308",
    ),
    "opaque-universal-result-cannot-escape": (
        """let beyond;
           { let local = 4; beyond = through(select_static, &local, &local); }
           println!("{}", beyond);""",
        "E0597",
    ),
    "generic-method-not-erasable": (
        """let erased: &dyn GenericIdentity = &Right;
           println!("{}", erased.identity(3));""",
        "E0038",
    ),
    "unbound-associated-type": (
        """let erased: &dyn Associated = &Right;
           println!("{}", erased.item());""",
        "E0191",
    ),
    "sized-generic-hidden-from-erased-interface": (
        """let erased: &dyn SizedGeneric = &Right;
           println!("{}", erased.map(3));""",
        "Sized",
    ),
}


def digest(raw):
    return sha256(raw).hexdigest()


def compile_client(root, rustc, optimization, name, snippet, expected):
    source = "use provider::*;\n\nfn main() {\n" + snippet + "\n}\n"
    path = root / f"{name}.rs"
    path.write_text(source, encoding="utf-8")
    flags = ["--edition=2021", "--error-format=json", "--remap-path-prefix", f"{root}=/fixture",
             "-C", f"opt-level={optimization}"]
    executable = f"{name}.out"
    check = subprocess.run(
        [rustc, *flags, path.name, "--extern", "provider=libprovider.rlib", "-o", executable],
        cwd=root, capture_output=True, text=True, check=False,
    )
    assert not check.stdout
    if isinstance(expected, str):
        assert check.returncode != 0
        errors = [report for line in check.stderr.splitlines()
                  if (report := json.loads(line))["level"] == "error"]
        codes = sorted({row["code"]["code"] for row in errors if row["code"] is not None})
        if expected.startswith("E"):
            assert expected in codes
        else:
            assert expected in errors[0]["rendered"], (name, errors[0]["message"])
        return {"decision": "refused", "requested_diagnostic": expected, "compiler_codes": codes}
    if check.returncode:
        raise AssertionError(check.stderr)
    assert not check.stderr
    raw = subprocess.check_output(["./" + executable], cwd=root)
    assert [int(line) for line in raw.splitlines()] == expected
    return {"decision": "admitted", "observations": len(expected), "observed_output": digest(raw)}


def experiment(work):
    rustc = os.environ.get("RUSTC", "rustc")
    payload = (HERE / "provider.rs").read_bytes()
    compiled = []
    rows = []
    for optimization in (0, 2):
        directory = work / f"O{optimization}"
        directory.mkdir()
        (directory / "provider.rs").write_bytes(payload)
        subprocess.run([rustc, "--edition=2021", "--crate-type=rlib", "-Dwarnings", "--remap-path-prefix",
                        f"{directory}=/fixture", "-C",
                        f"opt-level={optimization}", "provider.rs", "-o", "libprovider.rlib"],
                       cwd=directory, capture_output=True, check=True)
        compiled.append({"optimization": optimization,
                         "rlib": digest((directory / "libprovider.rlib").read_bytes())})
        for name, (snippet, expected) in CASES.items():
            row = compile_client(directory, rustc, optimization, name, snippet, expected)
            rows.append({"case": name, "optimization": optimization, **row})
    metrics = {
        "compile_decisions": len(rows), "accepted": sum(r["decision"] == "admitted" for r in rows),
        "native_observations": sum(r.get("observations", 0) for r in rows),
    }
    assert metrics == {"compile_decisions": 24, "accepted": 14, "native_observations": 1024}
    return {"format": "polymorphic-lifetimes-01", "compiler": subprocess.check_output(
        [rustc, "--version"], text=True).strip(), "provider_source": digest(payload),
        "provider_libraries": compiled, "metrics": metrics, "rows": rows}


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-polymorphic-lifetimes-") as directory:
        result = experiment(Path(directory))
    text = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
