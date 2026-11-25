"""Measure archive order, materialized link closure and exact ELF identities."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
from tempfile import TemporaryDirectory


MAIN = """#include <stdio.h>
extern unsigned increment(unsigned value);
int main(void)
{
    for (unsigned value = 0; value < 16; ++value)
        printf("%u\\n", increment(value));
}
"""
PROVIDER = "unsigned increment(unsigned value) { return value + STEP; }\n"
EXTRA = "unsigned fixture_marker(void) { return REVISION; }\n"
SCENARIOS = {
    "alpha_first": (("alpha", "beta", "extra_v1"), False, ("alpha.o",), 1),
    "beta_first": (("beta", "alpha", "extra_v1"), False, ("beta.o",), 2),
    "unselected_member_changed": (("alpha", "beta", "extra_v2"), False, ("alpha.o",), 1),
    "unselected_members_omitted": (("alpha",), False, ("alpha.o",), 1),
    "force_extra_member": (("alpha", "beta", "extra_v1"), True, ("alpha.o", "extra.o"), 1),
}
MEMBER = re.compile(r"^bundle\.a\(([^)]+)\)", re.MULTILINE)


def run(args, cwd, **kwargs):
    return subprocess.check_output(args, cwd=cwd, text=True, timeout=30, **kwargs)


def object_digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compile_obj(compiler, root, output, source):
    output.parent.mkdir(exist_ok=True)
    run([compiler, "-std=c17", "-Wall", "-Wextra", "-Werror", "-O2",
         "-x", "c", "-c", "-", "-o", str(output)], root, input=source)


def build(options, root):
    root.mkdir()
    objects = {
        "main": (root / "main.o", MAIN),
        "alpha": (root / "alpha.o", PROVIDER.replace("STEP", "1u")),
        "beta": (root / "beta.o", PROVIDER.replace("STEP", "2u")),
        "extra_v1": (root / "one" / "extra.o", EXTRA.replace("REVISION", "11u")),
        "extra_v2": (root / "two" / "extra.o", EXTRA.replace("REVISION", "12u")),
    }
    for obj, source in objects.values():
        compile_obj(options.cc, root, obj, source)
    cases = {}
    for name, (ordered, force, expected_members, step) in SCENARIOS.items():
        directory = root / name
        directory.mkdir()
        archive = directory / "bundle.a"
        paths = [objects[value][0] for value in ordered]
        run([options.ar, "rcsD", str(archive), *map(str, paths)], directory)
        names = run([options.ar, "t", "bundle.a"], directory).splitlines()
        assert names == [path.name for path in paths]
        flags = ["-Wl,-u,fixture_marker"] if force else []
        run([options.cc, str(objects["main"][0]), *flags, "bundle.a", "-Wl,--build-id=sha1,-Map=link.map",
             "-o", "program"], directory)
        selected = MEMBER.findall((directory / "link.map").read_text())
        assert sorted(set(selected)) == list(expected_members), selected
        artifact = directory / "program"
        behavior = [int(value) for value in run([str(artifact)], directory).splitlines()]
        assert behavior == list(range(step, 16 + step))
        cases[name] = {
            "archive_sha256": object_digest(archive),
            "ordered_members": [{"name": path.name, "sha256": object_digest(path)} for path in paths],
            "materialized_members": sorted(set(selected)),
            "linked_elf_sha256": object_digest(artifact),
            "output": behavior,
        }
    return cases


def study(options):
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        first = build(options, root / "first")
        assert first == build(options, root / "second")
        normal = first["alpha_first"]
        order = first["beta_first"]
        change = first["unselected_member_changed"]
        omit = first["unselected_members_omitted"]
        force = first["force_extra_member"]
        assert normal["archive_sha256"] != order["archive_sha256"]
        assert {item["sha256"] for item in normal["ordered_members"]} == {
            item["sha256"] for item in order["ordered_members"]
        }
        assert normal["linked_elf_sha256"] != order["linked_elf_sha256"]
        assert len({case["archive_sha256"] for case in (normal, change, omit)}) == 3
        assert normal["linked_elf_sha256"] == change["linked_elf_sha256"] == omit["linked_elf_sha256"]
        assert normal["archive_sha256"] == force["archive_sha256"]
        assert normal["linked_elf_sha256"] != force["linked_elf_sha256"]
        assert normal["output"] == force["output"] != order["output"]
        return {
            "python": platform.python_version(),
            "gcc": run([options.cc, "--version"], root).splitlines()[0],
            "archive_tool": run([options.ar, "--version"], root).splitlines()[0],
            "linker": run(["ld", "--version"], root).splitlines()[0],
            "fresh_build_roots": 2,
            "cases": first,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--ar", default="ar")
    print(json.dumps(study(parser.parse_args()), indent=2, sort_keys=True))
