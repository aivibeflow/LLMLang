"""Check finite reverse-call claims against actual C and shared-library dispatch."""
import argparse
import csv
from dataclasses import dataclass
from hashlib import sha256
import io
from itertools import product
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
REGISTRY_A = ("rule0", "rule1", "none", "rule0")
REGISTRY_B = ("rule1", "rule1", "rule0", "none")
SITES = ("direct-alpha", "direct-beta", "indirect", "generated", "dynamic-external")
TARGETS = ("local-alpha", "external-rule0-v1")


@dataclass(frozen=True)
class Profile:
    generated_key: int
    plugin_rule0: int
    registry: tuple[str, ...]
    closed: bool = True


PROFILES = {
    "baseline": Profile(2, 3000, REGISTRY_A),
    "changed-registry": Profile(2, 3000, REGISTRY_B),
    "changed-provider": Profile(2, 5000, REGISTRY_A),
    "changed-generator": Profile(1, 3000, REGISTRY_A),
    "open-selector-domain": Profile(2, 3000, REGISTRY_A, False),
}


def invoke(*args):
    return subprocess.run(args, text=True, capture_output=True, check=True, timeout=30,
                          env={**os.environ, "LC_ALL": "C"}).stdout.strip()


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def compile_fixtures(root, opt):
    apps = {}
    plugins = {}
    for key in sorted({p.generated_key for p in PROFILES.values()}):
        header = root / "generated.h"
        truth_table = ", ".join(str(int(other == key)) for other in range(4))
        header.write_text(f"static const int generated_alpha[] = {{ {truth_table} }};\n")
        app = root / f"app-{key}"
        invoke("gcc", "-std=c17", "-Wall", "-Wextra", "-Werror", f"-O{opt}",
               "-I", root, HERE / "probe.c", "-ldl", "-o", app)
        apps[key] = app
    for version in sorted({p.plugin_rule0 for p in PROFILES.values()}):
        plugin = root / f"plugin-{version}.so"
        invoke("gcc", "-std=c17", "-Wall", "-Wextra", "-Werror", f"-O{opt}",
               "-fPIC", "-shared", f"-DRULE0={version}", HERE / "plugin.c", "-o", plugin)
        plugins[version] = plugin
    assert len({digest(path) for path in apps.values()}) == len(apps)
    assert len({digest(path) for path in plugins.values()}) == len(plugins)
    return apps, plugins


def descriptor(profile):
    local_a, local_b = ("local-alpha",), ("local-beta",)
    external_a = ("external-rule0-v1",) if profile.plugin_rule0 == 3000 else ("external-rule0-v2",)
    external_names = {"rule0": external_a, "rule1": ("external-rule1",), "none": ()}
    return {
        ("direct-alpha", key): local_a for key in range(4)
    } | {
        ("direct-beta", key): local_b for key in range(4)
    } | {
        ("indirect", key): local_a if key in (0, 2) else local_b for key in range(4)
    } | {
        ("generated", key): local_a if key == profile.generated_key else local_b for key in range(4)
    } | {
        ("dynamic-external", key): external_names[symbol]
        for key, symbol in enumerate(profile.registry)
    }


def native(app, plugin, registry):
    decode = {1000: "local-alpha", 2000: "local-beta", 3000: "external-rule0-v1",
              4000: "external-rule1", 5000: "external-rule0-v2"}
    rows = list(csv.reader(io.StringIO(invoke(app, plugin, *registry))))
    calls = {}
    for site, key, value in rows:
        key, value = int(key), int(value)
        assert (site, key) not in calls
        calls[(site, key)] = (decode[value - key],) if value else ()
    assert set(calls) == set(product(SITES, range(4)))
    return calls


def uses(calls, target):
    return [[site, key] for (site, key), bindings in sorted(calls.items()) if target in bindings]


def profile_binding(profile, apps, plugins):
    return {
        "caller": digest(apps[profile.generated_key]),
        "provider": digest(plugins[profile.plugin_rule0]),
        "registry": sha256(json.dumps(profile.registry).encode()).hexdigest(),
        "closed": profile.closed,
    }


def compare(root, opt):
    apps, plugins = compile_fixtures(root, opt)
    bindings = {name: profile_binding(profile, apps, plugins) for name, profile in PROFILES.items()}
    rows = []
    results = []
    required_artifacts = ("caller", "provider", "registry")
    for name, profile in PROFILES.items():
        observed = native(apps[profile.generated_key], plugins[profile.plugin_rule0], profile.registry)
        assert observed == descriptor(profile)
        exact = {target: uses(observed, target) for target in TARGETS}
        results.append({"profile": name, "binding": bindings[name], "reverse": exact})
        for cached in PROFILES:
            for target in TARGETS:
                declared = uses(descriptor(PROFILES[cached]), target)
                direct = [row for row in declared if row[0].startswith("direct-")]
                admitted = profile.closed and bindings[cached] == bindings[name]
                disposition = "unknown" if not profile.closed else ("accepted" if admitted else "stale")
                if admitted:
                    assert exact[target] == declared
                omitted_binding_errors = [
                    omitted for omitted in required_artifacts
                    if profile.closed and declared != exact[target]
                    and all(bindings[cached][field] == bindings[name][field]
                            for field in (*required_artifacts, "closed") if field != omitted)
                ]
                rows.append({
                    "runtime": name, "receipt": cached, "target": target,
                    "direct_only_equal": direct == exact[target],
                    "unbound_descriptor_equal": declared == exact[target],
                    "pinned_disposition": disposition,
                    "incorrect_if_binding_omitted": omitted_binding_errors,
                })
    counts = {
        "native_dispatch_cases": len(PROFILES) * len(SITES) * 4,
        "receipt_queries": len(rows),
        "direct_only_incorrect": sum(not row["direct_only_equal"] for row in rows),
        "unbound_descriptor_incorrect": sum(not row["unbound_descriptor_equal"] for row in rows),
        "pinned_accepted": sum(row["pinned_disposition"] == "accepted" for row in rows),
        "pinned_stale": sum(row["pinned_disposition"] == "stale" for row in rows),
        "pinned_unknown": sum(row["pinned_disposition"] == "unknown" for row in rows),
        "incorrect_if_binding_omitted": {
            field: sum(field in row["incorrect_if_binding_omitted"] for row in rows)
            for field in required_artifacts
        },
    }
    assert counts["pinned_accepted"] == 8 and counts["pinned_stale"] == 32
    assert counts["pinned_unknown"] == 10 and counts["unbound_descriptor_incorrect"] == 22
    assert counts["direct_only_incorrect"] == 45
    assert counts["incorrect_if_binding_omitted"] == dict.fromkeys(required_artifacts, 2)
    return {"counts": counts, "profiles": results, "queries": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    builds = {}
    for opt in (0, 2):
        with TemporaryDirectory(prefix="llmlang-reverse-calls-") as directory:
            builds[f"O{opt}"] = compare(Path(directory), opt)
    assert builds["O0"]["queries"] == builds["O2"]["queries"]
    args.output.write_text(json.dumps({"gcc": invoke("gcc", "-dumpfullversion"), "builds": builds},
                                      indent=2) + "\n")


if __name__ == "__main__":
    main()
