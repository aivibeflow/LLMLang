#!/usr/bin/env python3
"""Collect exact per-action cache hits for a two-application native build."""

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
COMPONENTS = ("a", "b")
KINDS = ("compile", "archive", "link", "verify")
STAGES = ("cold", "warm", "comment_only", "local_value", "verification_policy", "shared_header",
          "restore_materialization")
ENV = {**os.environ, "LC_ALL": "C", "SOURCE_DATE_EPOCH": "0"}
CC = ("-std=c17", "-Wall", "-Wextra", "-Werror", "-O2")


def digest(value):
    return sha256(value).hexdigest()


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")


def command(args, cwd):
    return subprocess.run(args, cwd=cwd, env=ENV, check=True, capture_output=True,
                          timeout=25).stdout


def tools(root):
    records = {}
    for program in ("gcc", "ar", "as", "ld"):
        executable = program
        if program in ("as", "ld"):
            executable = command(["gcc", f"-print-prog-name={program}"], root).decode().strip()
        tool = Path(shutil.which(executable)).resolve()
        records[program] = {"version": command([tool, "--version"], root).decode().splitlines()[0],
                            "sha256": digest(tool.read_bytes())}
    records["target"] = command(["gcc", "-dumpmachine"], root).decode().strip()
    records["fixed_environment"] = {name: ENV[name] for name in ("LC_ALL", "SOURCE_DATE_EPOCH")}
    return records


def layout(root):
    (root / "out").mkdir(parents=True)


def sources(root, revision):
    (root / "shared.h").write_text(f"#define OFFSET {2 if revision >= 5 else 1}\n")
    for branch in COMPONENTS:
        if branch == "a":
            value = 8 if revision >= 3 else 5
        else:
            value = 11
        trivia = "/* wording only */\n" if branch == "a" and revision >= 2 else ""
        (root / f"lib_{branch}.c").write_text(
            f'#include "shared.h"\n{trivia}int value_{branch}(void) {{ return {value} + OFFSET; }}\n'
        )
        (root / f"main_{branch}.c").write_text(
            f'#include <stdio.h>\nint value_{branch}(void);\n'
            f'int main(void) {{ printf("%d\\n", value_{branch}()); return 0; }}\n'
        )


@dataclass(frozen=True)
class Payload:
    action: str
    content: str


class Runner:
    def __init__(self, root, policy, tool_context):
        layout(root)
        self.root = root
        self.policy = policy
        self.tool_context = tool_context
        self.cache = {}

    def inputs(self, payloads):
        return [item.action if self.policy == "producer_keys" else item.content for item in payloads]

    def perform(self, kind, action, ingredients, output, build, *, executable=False):
        token = digest(encode([kind, action, ingredients, self.tool_context, CC]))
        missing = not output.exists()
        hit = self.policy != "forced" and token in self.cache
        if hit:
            expected, value = self.cache[token]
            if digest(value) != expected:
                raise AssertionError("Cache payload failed verification")
            needs_restore = missing or output.read_bytes() != value
            if needs_restore:
                output.write_bytes(value)
                if executable:
                    output.chmod(0o755)
        else:
            output.unlink(missing_ok=True)
            build()
            value = output.read_bytes()
            expected = digest(value)
            self.cache[token] = expected, value
            needs_restore = False
        self.rows.append({"kind": kind, "action": action, "hit": hit,
                          "materialized_from_cache": needs_restore, "key": token, "payload": expected})
        return Payload(token, expected)

    def build(self, revision):
        sources(self.root, revision)
        out = self.root / "out"
        if revision == 6:
            for path in out.iterdir():
                path.unlink()
        self.rows = []
        observed = {}
        for branch in COMPONENTS:
            object_files = {}
            for unit in ("main", "lib"):
                name = f"{unit}_{branch}"
                source = f"{name}.c"
                output = out / f"{name}.o"
                closure = [source, "shared.h"] if unit == "lib" else [source]
                fingerprints = [digest((self.root / path).read_bytes()) for path in closure]
                object_files[unit] = self.perform(
                    "compile", name, fingerprints, output,
                    lambda: command(["gcc", *CC, "-c", source, "-o", output], self.root),
                )
            archive = out / f"lib_{branch}.a"
            archive_object = out / f"lib_{branch}.o"
            library = self.perform(
                "archive", f"library_{branch}", self.inputs([object_files["lib"]]), archive,
                lambda: command(["ar", "rcD", archive, archive_object], self.root),
            )
            app = out / f"app_{branch}"
            main_object = out / f"main_{branch}.o"
            executable = self.perform(
                "link", f"link_{branch}", self.inputs([object_files["main"], library]), app,
                lambda: command(["gcc", main_object, archive, "-Wl,--build-id=none", "-o", app], self.root),
                executable=True,
            )

            threshold = 1000 if branch == "a" and revision >= 4 else 0
            receipt = out / f"verify_{branch}.json"
            verified_inputs = self.inputs([executable])
            if self.policy != "no_verifier_policy":
                verified_inputs.append({"minimum": threshold})

            def verify():
                value = int(command([app], self.root))
                receipt.write_bytes(encode({"observed": value, "satisfied": value >= threshold,
                                            "minimum": threshold}))

            self.perform("verify", f"verify_{branch}", verified_inputs, receipt, verify)
            observed[branch] = json.loads(receipt.read_text())
        hits = Counter(row["kind"] for row in self.rows if row["hit"])
        total = Counter(row["kind"] for row in self.rows)
        return {
            "hits": {kind: hits[kind] for kind in KINDS},
            "actions": {kind: total[kind] for kind in KINDS},
            "restored": sum(row["materialized_from_cache"] for row in self.rows),
            "observations": observed, "rows": self.rows,
            "artifacts": {path.name: digest(path.read_bytes()) for path in sorted(out.iterdir())},
        }


def run():
    policies = ("exact_payload", "producer_keys", "no_verifier_policy", "forced")
    with TemporaryDirectory(prefix="llmlang-multi-action-") as temporary:
        root = Path(temporary)
        tool_data = tools(root)
        runners = {policy: Runner(root / policy, policy, digest(encode(tool_data))) for policy in policies}
        results = {}
        for revision, stage in enumerate(STAGES):
            matrix = {policy: runner.build(revision) for policy, runner in runners.items()}
            oracle = matrix["forced"]["artifacts"]
            for policy in ("exact_payload", "producer_keys"):
                if matrix[policy]["artifacts"] != oracle:
                    raise AssertionError((stage, policy, matrix[policy]["artifacts"], oracle))
            hidden = matrix["no_verifier_policy"]["observations"]["a"]
            reported = matrix["forced"]["observations"]["a"]
            if (hidden != reported) != (stage == "verification_policy"):
                raise AssertionError((stage, hidden, reported))
            results[stage] = matrix

    vanilla = results["comment_only"]["exact_payload"]
    propagated = results["comment_only"]["producer_keys"]
    if vanilla["hits"] != {"compile": 3, "archive": 2, "link": 2, "verify": 2}:
        raise AssertionError(vanilla["hits"])
    if propagated["hits"] != {"compile": 3, "archive": 1, "link": 1, "verify": 1}:
        raise AssertionError(propagated["hits"])
    if vanilla["artifacts"] != results["warm"]["exact_payload"]["artifacts"]:
        raise AssertionError("The comment unexpectedly changed a native artifact")
    if results["restore_materialization"]["exact_payload"]["restored"] != 10:
        raise AssertionError("Warm cache did not rematerialize every missing output")
    return {
        "schema": "llmlang-multi-action-cache/1", "python": platform.python_version(),
        "tools": tool_data, "inputs_sha256": {"run.py": digest(Path(__file__).read_bytes())},
        "phases": results,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
