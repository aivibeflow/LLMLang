"""Pin and reconcile small C and Python source baselines in a disposable Git repository."""

import argparse
import ast
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import re
import subprocess
from tempfile import TemporaryDirectory


BASE = {
    "leaf.c": "int add(int x) { return x + 1; }\n",
    "root.py": "def root(x):\n    return add(x)\n",
    "spare.py": "def spare(x):\n    return x + 1\n",
    "build.flags": "-std=c11\n",
}
ENTITIES = {"leaf": ["leaf.c", "add"], "root": ["root.py", "root"], "spare": ["spare.py", "spare"]}
CASES = (
    ("trivia", {"leaf.c": "int add(int x) {\n    return x+1;\n}\n"}, {}, "trivia", [], []),
    ("implementation", {"leaf.c": "int add(int x) { return x+2; }\n"}, {},
     "affected", ["leaf", "root"], []),
    ("rename", {"leaf.c": None, "increment.c": "int increment(int x) { return x+1; }\n",
                "root.py": "def root(x):\n    return increment(x)\n"},
     {"leaf": ["increment.c", "increment"]}, "affected", ["leaf", "root"], ["leaf"]),
    ("uncorrelated_rename", {"leaf.c": None, "increment.c": "int increment(int x) { return x+1; }\n"},
     {}, "blocked", ["leaf", "root", "spare"], []),
    ("dependency", {"root.py": "def root(x):\n    return spare(x)\n"}, {}, "affected", ["root"], []),
    ("interface", {"root.py": "def root(x, y):\n    return add(x)\n"}, {}, "affected", ["root"], ["root"]),
    ("unreviewed_removal", {"leaf.c": None}, {}, "blocked", ["leaf", "root", "spare"], []),
    ("duplicate_binding", {"clone.py": "def clone(x):\n    return x + 1\n"},
     {"spare": ["root.py", "root"]}, "blocked", ["leaf", "root", "spare"], []),
    ("reflection", {"root.py": "def root(x):\n    return globals()['add'](x)\n"},
     {}, "blocked", ["leaf", "root", "spare"], []),
    ("shadowed_call", {"root.py": "def root(add):\n    return add(add)\n"},
     {}, "blocked", ["leaf", "root", "spare"], []),
    ("operand", {"root.py": "def root(x, y):\n    return y + 1\n"},
     {}, "affected", ["root"], ["root"]),
    ("macro", {"leaf.c": "#define N 2\nint add(int x) { return x + N; }\n"},
     {}, "blocked", ["leaf", "root", "spare"], []),
    ("build_profile", {"build.flags": "-std=gnu11\n"}, {}, "blocked", ["leaf", "root", "spare"], []),
    ("untracked_source", {"clone.py": "def clone(x):\n    return x + 1\n"}, {},
     "blocked", ["leaf", "root", "spare"], []),
)
C_FORM = re.compile(r"int\s+(\w+)\s*\(\s*int\s+(\w+)\s*\)\s*\{\s*return\s+(\w+)\s*\+\s*([0-9])\s*;\s*\}")


def digest(record):
    return sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def invoke(args, cwd, env, data=None):
    return subprocess.run(args, cwd=cwd, env=env, input=data, capture_output=True,
                          check=True, timeout=30).stdout


def c_profile(source, name, clang, repo, env):
    match = C_FORM.fullmatch(source.strip())
    if match is None or match[1] != name or match[2] != match[3]:
        raise ValueError("unsupported-c-shape")
    profile = json.loads(invoke([clang, "-std=c11", "-x", "c", "-fsyntax-only", "-Xclang",
                                 "-ast-dump=json", "-"], repo, env, source.encode()))
    functions = [node for node in profile["inner"] if node["kind"] == "FunctionDecl"]
    if len(functions) != 1 or functions[0]["name"] != name:
        raise ValueError("unexpected-c-frontend")
    parameter, compound = functions[0]["inner"]
    statement, = compound["inner"]
    binary, = statement["inner"]
    left, right = binary["inner"]
    reference, = left["inner"]
    if (binary["opcode"], reference["referencedDecl"]["name"], right["value"]) != ("+", match[2], match[4]):
        raise ValueError("unexpected-c-expression")
    return ("c", name, [parameter["type"]["qualType"]], ["add-literal", int(right["value"])], [])


def python_profile(source, name):
    nodes = ast.parse(source).body
    if len(nodes) != 1 or not isinstance(nodes[0], ast.FunctionDef) or nodes[0].name != name:
        raise ValueError("unsupported-python-module")
    fn = nodes[0]
    params = fn.args
    if (fn.decorator_list or fn.returns or params.posonlyargs or params.kwonlyargs
            or params.vararg or params.kwarg or params.defaults
            or any(p.annotation for p in params.args)
            or len(fn.body) != 1 or not isinstance(fn.body[0], ast.Return)):
        raise ValueError("unsupported-python-signature")
    names = [p.arg for p in params.args]
    expr = fn.body[0].value
    if (isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name) and not expr.keywords
            and expr.func.id not in names and len(expr.args) == 1 and isinstance(expr.args[0], ast.Name) and expr.args[0].id in names):
        return ("python", name, names, ["call", names.index(expr.args[0].id)], [expr.func.id])
    if (isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add) and isinstance(expr.left, ast.Name)
            and expr.left.id in names and isinstance(expr.right, ast.Constant)
            and type(expr.right.value) is int):
        return ("python", name, names, ["add-literal", names.index(expr.left.id), expr.right.value], [])
    raise ValueError("unsupported-python-expression")


def inventory(git, repo, env, clang, commit):
    def read(path):
        return git("show", f"{commit}:{path}").decode()

    paths = git("ls-tree", "-r", "--name-only", commit).decode().splitlines()
    bindings = json.loads(read("bindings.json"))
    if set(bindings) != set(ENTITIES):
        raise ValueError("unreviewed-unit-set")
    names = [record[1] for record in bindings.values()]
    sources = [record[0] for record in bindings.values()]
    if len(set(names)) != len(names) or len(set(sources)) != len(sources):
        raise ValueError("ambiguous-binding")
    if {path for path in paths if path.endswith((".py", ".c"))} != set(sources):
        raise ValueError("incomplete-source-inventory")
    if read("build.flags") != BASE["build.flags"]:
        raise ValueError("unsupported-build-profile")
    by_name = {name: unit for unit, (_, name) in bindings.items()}
    records = {}
    for unit, (path, name) in sorted(bindings.items()):
        source = read(path)
        language, symbol, signature, body, calls = (c_profile(source, name, clang, repo, env)
            if path.endswith(".c") else python_profile(source, name))
        if any(call not in by_name for call in calls):
            raise ValueError("unresolved-call")
        deps = [by_name[target] for target in calls]
        records[unit] = {
            "occurrence": digest([commit, path, symbol, git("rev-parse", f"{commit}:{path}").decode().strip()]),
            "binding": digest([unit, language, path, symbol, signature, f"mirror:{unit}"]),
            "semantic": digest([language, signature, body, deps]), "dependencies": deps,
        }
    return records


def reconcile(before, after):
    changed = {unit for unit, row in after.items()
               if any(row[key] != before[unit][key] for key in ("binding", "semantic"))}
    impacted = set(changed)
    while True:
        added = {unit for inventory in (before, after) for unit, row in inventory.items()
                 if any(dep in impacted for dep in row["dependencies"])} - impacted
        if not added:
            break
        impacted.update(added)
    return sorted(impacted), sorted(unit for unit in after if after[unit]["binding"] != before[unit]["binding"])


def check(clang, repo):
    env = {**os.environ, "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_AUTHOR_NAME": "Research Fixture",
           "GIT_AUTHOR_EMAIL": "fixture@example.invalid", "GIT_COMMITTER_NAME": "Research Fixture",
           "GIT_COMMITTER_EMAIL": "fixture@example.invalid", "GIT_AUTHOR_DATE": "2020-01-01T00:00:00Z",
           "GIT_COMMITTER_DATE": "2020-01-01T00:00:00Z"}

    def git(*args):
        return invoke(["git", *args], repo, env)

    def write(files, entities):
        for path, text in files.items():
            p = repo / path
            if text is None:
                p.unlink()
            else:
                p.write_text(text)
        (repo / "bindings.json").write_text(json.dumps(entities, sort_keys=True) + "\n")

    def commit(message):
        git("add", "-A")
        git("-c", "commit.gpgsign=false", "commit", "-qm", message)
        return git("rev-parse", "HEAD").decode().strip()

    git("init", "-q", "-b", "research/all", "--object-format=sha256")
    write(BASE, ENTITIES)
    start = commit("fixture baseline")
    before = inventory(git, repo, env, clang, start)
    results = {}
    for name, files, entries, expected, impacts, revisions in CASES:
        git("reset", "--hard", start)
        write(files, ENTITIES | entries)
        head = commit(name)
        try:
            after = inventory(git, repo, env, clang, head)
        except ValueError as error:
            row = ("blocked", sorted(before), [])
            reason = str(error)
        else:
            impacted, updated = reconcile(before, after)
            row = ("affected" if impacted else "trivia", impacted, updated)
            reason = ""
            assert all(before[unit]["occurrence"] != after[unit]["occurrence"] for unit in before)
        assert row == (expected, impacts, revisions), (name, row)
        results[name] = dict(commit=head, tree=git("rev-parse", f"{head}^{{tree}}").decode().strip(),
                             after_units=None if reason else after, disposition=row[0], impacted=row[1], binding_revisions=row[2], reason=reason)
    return {
        "baseline": start, "baseline_tree": git("rev-parse", f"{start}^{{tree}}").decode().strip(),
        "baseline_units": before, "cases": results,
        "summary": dict(Counter(row["disposition"] for row in results.values())),
        "git": git("--version").decode().strip(),
        "python": platform.python_version(),
        "clang": invoke([clang, "--version"], repo, env).decode().splitlines()[0],
        "clang_sha256": sha256(Path(clang).read_bytes()).hexdigest(),
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="rt28-source-binding-") as temporary:
        print(json.dumps(check(args.clang, Path(temporary)), sort_keys=True, indent=2))
