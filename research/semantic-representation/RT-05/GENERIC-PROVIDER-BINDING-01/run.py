#!/usr/bin/env python3
"""Compare native generic dispatch and reuse across independently built providers."""

from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import platform
import random
import re
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROUTES = ("static", "linked", "trait", "dictionary")
VARIANTS = {"original": (13, 77), "body_edit": (19, 77), "unrelated_edit": (13, 84)}
SEED = 20261125
MASK = (1 << 64) - 1
LIMIT = 1 << 63
EDGE_INPUTS = (-LIMIT, -LIMIT + 1, -257, -1, 0, 1, 257, LIMIT - 1)
FIXTURE_FILES = ("provider.rs.in", "consumer.rs", "driver.c", "run.py")
TOOLCHAIN = ("--edition", "2021", "-C", "metadata=rt05_scope", "-C", "panic=abort")


def digest(data):
    return sha256(data).hexdigest()


def cmd(directory, *arguments, data=None):
    result = subprocess.run(arguments, cwd=directory, input=data, capture_output=True, check=False,
                            text=True, timeout=45, env={**os.environ, "LC_ALL": "C"})
    assert result.returncode == 0, (arguments, result.stdout, result.stderr)
    return result.stdout


def inputs():
    generator = random.Random(SEED)
    corpus = [*EDGE_INPUTS, *(generator.randrange(-LIMIT, LIMIT) for _ in range(120))]
    assert len(set(corpus)) == len(corpus) == 128
    return list(product((0, 1), corpus))


def reference(tag, value, amber_add):
    result = (3 * value + amber_add if tag == 0 else 5 * value - 7) & MASK
    return result - (1 << 64) if result >= LIMIT else result


def disassembly(directory, consumer):
    wrapper_sizes = {}
    specializations = {"inline": [], "linked": []}
    for row in cmd(directory, "nm", "--defined-only", "--print-size", str(consumer)).splitlines():
        _, size, kind, name = row.split()
        if name.startswith("route_"):
            assert kind == "T"
            wrapper_sizes[name.removeprefix("route_")] = int(size, 16)
        for specialization, sizes in specializations.items():
            if f"specialized_{specialization}" in name:
                assert kind == "t"
                sizes.append(int(size, 16))
    assert set(wrapper_sizes) == set(ROUTES) and all(len(sizes) == 2 for sizes in specializations.values())
    dynamic_branches = dict.fromkeys(ROUTES, 0)
    active = None
    for row in cmd(directory, "objdump", "-drw", str(consumer)).splitlines():
        function = re.fullmatch(r"[0-9a-f]+ <(\w+)>:", row)
        if function:
            active = function[1].removeprefix("route_")
        if active in dynamic_branches and "R_X86_64_" not in row and re.search(r"\b(?:call|jmp)\s+\*", row):
            dynamic_branches[active] += 1
    return {"wrapper_text_bytes": wrapper_sizes, "specialization_text_bytes": {name: sorted(sizes) for name, sizes in specializations.items()},
            "computed_branches": dynamic_branches}


def prepare(directory, revision, opt):
    directory.mkdir()
    amber_add, unrelated = VARIANTS[revision]
    template = (HERE / "provider.rs.in").read_text(encoding="utf-8")
    provider = template.replace("@AMBER_ADD@", str(amber_add)).replace("@UNRELATED@", str(unrelated))
    (directory / "provider.rs").write_text(provider, encoding="utf-8")
    (directory / "consumer.rs").write_bytes((HERE / "consumer.rs").read_bytes())
    (directory / "driver.c").write_bytes((HERE / "driver.c").read_bytes())
    cmd(directory, "rustc", *TOOLCHAIN, "-C", f"opt-level={opt}", "--crate-name", "routes_provider",
        "--crate-type", "rlib,staticlib", "provider.rs")
    cmd(directory, "rustc", *TOOLCHAIN, "-C", f"opt-level={opt}", "--crate-name", "routes_consumer",
        "--crate-type", "lib", "--extern", "routes_provider=libroutes_provider.rlib",
        "--emit", "obj=consumer.o", "consumer.rs")
    consumer = directory / "consumer.o"
    blob = consumer.read_bytes()
    return {"provider_source_sha256": digest(provider.encode()),
            "provider_archive_sha256": digest((directory / "libroutes_provider.a").read_bytes()),
            "consumer_object_sha256": digest(blob),
            "consumer_object_bytes": len(blob), **disassembly(directory, consumer)}


def link_and_run(directory, consumer, provider, cases):
    cmd(directory, "gcc", "-Os", "-Wl,--gc-sections", "driver.c", str(consumer / "consumer.o"),
        str(provider / "libroutes_provider.a"), "-ldl", "-lpthread", "-lm", "-o", "trial")
    raw = "".join(f"{tag} {value}\n" for tag, value in cases)
    result = cmd(directory, "./trial", data=raw).splitlines()
    marker = int(result[0].removeprefix("provider "))
    vector = [list(map(int, line.split())) for line in result[1:]]
    assert len(vector) == len(cases) and all(len(row) == len(ROUTES) for row in vector)
    return marker, vector


def compare(directory, opt, cases):
    artifacts = {name: prepare(directory / name, name, opt) for name in VARIANTS}
    evidence = []
    for consumer, provider in product(VARIANTS, repeat=2):
        marker, outputs = link_and_run(directory / provider, directory / consumer, directory / provider, cases)
        assert marker == VARIANTS[provider][1]
        expected = [reference(tag, value, VARIANTS[provider][0]) for tag, value in cases]
        old_body = [reference(tag, value, VARIANTS[consumer][0]) for tag, value in cases]
        mismatches = dict.fromkeys(ROUTES, 0)
        for seen, old, current in zip(outputs, old_body, expected, strict=True):
            assert seen == [old, current, current, current], (opt, consumer, provider, seen, old, current)
            for route, value in zip(ROUTES, seen, strict=True):
                mismatches[route] += value != current
        evidence.append({"opt": opt, "consumer": consumer, "provider": provider, "provider_marker": marker,
                         "mismatches": mismatches, "observations": outputs})
    return artifacts, evidence


def run(directory):
    assert platform.machine() == "x86_64" and platform.system() == "Linux"
    cases = inputs()
    artifacts, rows = {}, []
    for opt in (0, 3):
        with TemporaryDirectory(prefix=f"O{opt}-", dir=directory) as stage:
            data, observed = compare(Path(stage), opt, cases)
        artifacts[f"O{opt}"] = data
        rows.extend(observed)
        assert len({variant["provider_archive_sha256"] for variant in data.values()}) == len(VARIANTS)
        assert data["original"]["consumer_object_sha256"] == data["unrelated_edit"]["consumer_object_sha256"]
        assert data["original"]["consumer_object_sha256"] != data["body_edit"]["consumer_object_sha256"]
    for variant in artifacts["O3"].values():
        counts = variant["computed_branches"]
        assert counts["static"] == counts["linked"] == 0 and counts["trait"] == counts["dictionary"] == 1
    metrics = {str(opt): {route: sum(row["mismatches"][route] for row in rows if row["opt"] == opt)
                          for route in ROUTES} for opt in (0, 3)}
    return {"schema": "llmlang-rt05-generic-provider-binding/1", "python": platform.python_version(),
            "rustc": cmd(directory, "rustc", "-vV").splitlines(),
            "gcc": cmd(directory, "gcc", "--version").splitlines()[0],
            "objdump": cmd(directory, "objdump", "--version").splitlines()[0], "seed": SEED,
            "sources": {name: digest((HERE / name).read_bytes()) for name in FIXTURE_FILES},
            "variants": VARIANTS, "cases": cases, "artifacts": artifacts,
            "linked_binaries": len(rows), "native_values": len(rows) * len(cases) * len(ROUTES),
            "metrics": metrics, "observations": rows}


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-rt05-generic-") as scratch:
        result = run(Path(scratch))
    rows = result.pop("observations")
    print(json.dumps(result, indent=2).removesuffix("\n}") + ',\n  "observations": [')
    print(",\n".join("    " + json.dumps(row, separators=(",", ":")) for row in rows))
    print("  ]\n}")
