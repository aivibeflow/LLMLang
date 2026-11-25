#!/usr/bin/env python3
"""Measure configuration-bound reverse caller coverage using native C builds and RT-20."""

from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import platform
import re
from shutil import which
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
PROTOTYPE = HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"
sys.path.insert(0, str(PROTOTYPE))
from src.impact_planning import (ActionKind, CompletenessAudit, CompletenessStatus,
                                 ImpactedArtifact, IncomingCallSite, plan_impact)

DOMAIN = "llmlang-rt24-configuration-bound-callers/1"
POLICIES = ("source_only", "source_and_flags", "all_profile_union", "exact_profile")
SITES = ("site_primary", "site_secondary", "site_optional")
FLAGS = ("MODE", "AUDIT", "EXTRA")
CONFIGURATIONS = tuple(product((0, 1), repeat=len(FLAGS)))
OPTIMIZATIONS = ("O0", "O2")
REVISIONS = ("original", "edited")
VALUES = {"provider_base": 17, "provider_amber": 29, "provider_cobalt": 41, "provider_audit": 53}
INVENTORY = ("client.c", "include/routes.h", "include/selected.inc")
FIXTURE_FILES = ("client.c", "routes.h", "providers.c", "driver.c", "run.py")
DECLARATIONS = {
    "original": "#define PRIMARY provider_cobalt\n#define SECONDARY provider_base\n#define OPTIONAL provider_amber\n",
    "edited": "#define PRIMARY provider_amber\n#define SECONDARY provider_cobalt\n#define OPTIONAL provider_cobalt\n",
}


def digest(data):
    return sha256(data).hexdigest()


def identity(value):
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return digest(DOMAIN.encode() + b"\0" + canonical)


def cmd(directory, *arguments):
    return subprocess.run(arguments, cwd=directory, check=True, capture_output=True, text=True, timeout=30,
                          env={**os.environ, "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
                               "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
                               "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
                               "GIT_AUTHOR_DATE": "2026-11-25T00:00:00Z", "GIT_COMMITTER_DATE": "2026-11-25T00:00:00Z"}).stdout


def git(directory, *arguments):
    return cmd(directory, "git", *arguments).strip()


def source_history(repo):
    git(repo, "init", "-q", "-b", "main", "--object-format=sha1")
    (repo / "include").mkdir()
    for source in ("client.c", "providers.c", "driver.c"):
        (repo / source).write_bytes((HERE / source).read_bytes())
    (repo / "include/routes.h").write_bytes((HERE / "routes.h").read_bytes())
    commits = {}
    for name, header in DECLARATIONS.items():
        (repo / "include/selected.inc").write_text(header, encoding="utf-8")
        git(repo, "add", "--", "client.c", "providers.c", "driver.c", "include")
        git(repo, "commit", "-q", "-m", name)
        commits[name] = git(repo, "rev-parse", "HEAD")
    assert git(repo, "diff", "--name-only", *commits.values()) == "include/selected.inc"
    return commits


def oracle(revision, profile):
    mode, audit, extra = profile
    edited = revision == "edited"
    primary = ("provider_amber" if edited else "provider_cobalt") if mode else "provider_base"
    secondary = "provider_audit" if audit else ("provider_cobalt" if edited else "provider_base")
    optional = ("provider_cobalt" if edited else "provider_amber") if extra else None
    return dict(zip(SITES, (primary, secondary, optional), strict=True))


def relocations(disassembly):
    edges = set()
    site = None
    for line in disassembly.splitlines():
        symbol = re.fullmatch(r"[0-9a-f]+ <(\w+)>:", line)
        if symbol:
            site = symbol[1]
            assert site in SITES, line
            continue
        if "R_X86_64_" in line:
            reloc = re.search(r"\bR_X86_64_PLT32\s+(provider_\w+)-0x4\s*$", line)
            assert reloc and site in SITES and reloc[1] in VALUES, line
            edge = site, reloc[1]
            assert edge not in edges, line
            edges.add(edge)
    return edges


def native_build(repo, revision, config, opt, tool, inventory, tree):
    flags = [f"-D{name}={value}" for name, value in zip(FLAGS, config, strict=True)]
    arguments = [f"-{opt}", "-Iinclude", *flags, "-fno-optimize-sibling-calls", "-Wall", "-Werror",
                 "-MMD", "-MF", "client.d", "-c", "client.c", "-o", "client.o"]
    cmd(repo, "gcc", *arguments)
    dependencies = (repo / "client.d").read_text().replace("\\\n", " ").split(":", 1)[1].split()
    assert set(dependencies) == set(INVENTORY) and len(dependencies) == len(INVENTORY)
    edges = relocations(cmd(repo, "objdump", "-drw", "client.o"))
    expected = oracle(revision, config)
    assert edges == {(site, target) for site, target in expected.items() if target is not None}, (revision, config, edges)
    cmd(repo, "gcc", f"-{opt}", "client.o", "providers.c", "driver.c", "-o", "client")
    observed = [int(value) for value in cmd(repo, "./client").split()]
    assert observed == [VALUES.get(expected[site], 0) for site in SITES]
    manifest = {"tree": tree, "tool": tool, "arguments": arguments, "dependencies": inventory}
    return {"manifest": manifest, "profile_id": identity(manifest), "edges": sorted(edges),
            "object_sha256": digest((repo / "client.o").read_bytes()), "native_result": observed}


def planner(profile_id, edges, targets, caller_digest, status):
    audit_rows = []
    for provider, target in targets.items():
        sites = tuple(IncomingCallSite(caller_digest, site, provider, target,
                                       required_contract_hash=identity("return signed C int"))
                      for site, name in edges if name == provider)
        encoded = [(row.caller_hash, row.call_site_id, row.target_id, row.target_hash) for row in sites]
        audit_rows.append(CompletenessAudit(status, (), target, profile_id, "ELF relocation fixture", DOMAIN,
                          snapshot_root=profile_id, target_hash=target, evidence_id=identity(encoded),
                          edge_set_digest=identity(encoded), index_schema_version=1,
                          extractor_id="gnu-x86-64-reloc-v1", incoming_call_sites=sites))
    change = [ImpactedArtifact(target, "implementation", "compare callers") for target in targets.values()]
    plan = plan_impact(profile_id, profile_id, DOMAIN, change, audit_rows)
    revalidate = any(action.kind is ActionKind.FULL_REVALIDATION for action in plan.actions)
    prefix = "every discovered call-site edge needs an evidence-backed disposition: "
    obligations = sorted(edge for item in plan.actions if item.reason.startswith(prefix)
                         for edge in item.reason.removeprefix(prefix).split(", "))
    expected = sorted(f"{caller_digest}:{site}/{target}" for site, target in edges)
    assert obligations == expected
    coverage_unknown = any(value != CompletenessStatus.SUPPORTED_WITHIN_SCOPE.value
                           for _, value in plan.audit_statuses)
    return {"unresolved_call_site_edges": obligations, "full_revalidation": revalidate,
            "coverage_unknown": coverage_unknown}


def compare(rows, targets, caller_digest):
    metrics = {policy: dict(exact=0, missing_edges=0, excess_edges=0, coverage_unknown=0) for policy in POLICIES}
    controls = {"revision": {"old_edge_set_equal": 0, "edge_only_accepts": 0, "profile_accepts": 0},
                "optimization": {"old_edge_set_equal": 0, "edge_only_accepts": 0, "profile_accepts": 0}}
    for (revision, config, opt), row in rows.items():
        wanted = set(row["edges"])
        union = set().union(*(candidate["edges"] for key, candidate in rows.items()
                              if key[0] == revision and key[2] == opt))
        predictions = {
            "source_only": set(rows[("original", (0, 0, 0), opt)]["edges"]),
            "source_and_flags": set(rows[("original", config, opt)]["edges"]),
            "all_profile_union": union,
            "exact_profile": wanted,
        }
        row["policies"] = {}
        for policy, predicted in predictions.items():
            missing, excess = sorted(wanted - predicted), sorted(predicted - wanted)
            result = planner(row["profile_id"], sorted(predicted), targets, caller_digest,
                             CompletenessStatus.SUPPORTED_WITHIN_SCOPE)
            metrics[policy]["exact"] += not missing and not excess
            metrics[policy]["missing_edges"] += len(missing)
            metrics[policy]["excess_edges"] += len(excess)
            metrics[policy]["coverage_unknown"] += result["coverage_unknown"]
            row["policies"][policy] = {"missing": missing, "excess": excess, "planner": result}
        other_revision = "edited" if revision == "original" else "original"
        other_opt = "O2" if opt == "O0" else "O0"
        replays = {"revision": rows[(other_revision, config, opt)], "optimization": rows[(revision, config, other_opt)]}
        row["replay_controls"] = {}
        for label, receipt in replays.items():
            equal_edges = receipt["edges"] == row["edges"]
            accepted = equal_edges and receipt["profile_id"] == row["profile_id"]
            assert not accepted
            result = planner(row["profile_id"], [], targets, caller_digest, CompletenessStatus.UNKNOWN)
            assert result["full_revalidation"] and result["coverage_unknown"]
            controls[label]["old_edge_set_equal"] += equal_edges
            controls[label]["edge_only_accepts"] += equal_edges
            controls[label]["profile_accepts"] += accepted
            row["replay_controls"][label] = {"old_profile": receipt["profile_id"], "equal_edges": equal_edges,
                                              "profile_accepted": accepted, "planner": result}
    return metrics, controls


def run(repo):
    assert platform.machine() == "x86_64" and platform.system() == "Linux"
    executable_names = ("gcc", "objdump", "ld")
    binaries = {name: digest(Path(which(name)).read_bytes()) for name in executable_names}
    cc1 = Path(cmd(repo, "gcc", "-print-prog-name=cc1").strip())
    binaries["cc1"] = digest(cc1.read_bytes())
    tool = {"versions": {name: cmd(repo, name, "--version").splitlines()[0] for name in executable_names},
            "target": cmd(repo, "gcc", "-dumpmachine").strip(), "executable_sha256": binaries}
    commits = source_history(repo)
    caller_digest = digest((repo / "client.c").read_bytes())
    provider_digest = digest((repo / "providers.c").read_bytes())
    targets = {provider: identity((provider, provider_digest)) for provider in VALUES}
    rows = {}
    for revision, commit in commits.items():
        git(repo, "checkout", "-q", "--detach", commit)
        tree = git(repo, "rev-parse", "HEAD^{tree}")
        inventory = {path: {"blob": git(repo, "rev-parse", f"{commit}:{path}"),
                            "sha256": digest((repo / path).read_bytes())} for path in INVENTORY}
        assert caller_digest == inventory["client.c"]["sha256"]
        for config, opt in product(CONFIGURATIONS, OPTIMIZATIONS):
            row = native_build(repo, revision, config, opt, tool, inventory, tree)
            rows[(revision, config, opt)] = {"revision": revision, "config": config, "optimization": opt, **row}
    metrics, controls = compare(rows, targets, caller_digest)
    assert metrics["exact_profile"] == dict(exact=len(rows), missing_edges=0, excess_edges=0, coverage_unknown=0)
    assert metrics["source_only"]["missing_edges"] > metrics["source_and_flags"]["missing_edges"] > 0
    assert metrics["all_profile_union"]["missing_edges"] == 0 < metrics["all_profile_union"]["excess_edges"]
    assert controls["optimization"]["old_edge_set_equal"] == len(rows)
    return {"schema": DOMAIN, "python": platform.python_version(), "git": git(repo, "--version"), "tool": tool,
            "sources": {name: digest((HERE / name).read_bytes()) for name in FIXTURE_FILES},
            "impact_planner_sha256": digest((PROTOTYPE / "src" / "impact_planning.py").read_bytes()),
            "commits": commits, "native_profiles": len(rows), "metrics": metrics, "replay_controls": controls,
            "observations": list(rows.values())}


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-rt24-config-callers-") as scratch:
        result = run(Path(scratch))
    rows = result.pop("observations")
    print(json.dumps(result, indent=2).removesuffix("\n}") + ',\n  "observations": [')
    print(",\n".join("    " + json.dumps(row, separators=(",", ":")) for row in rows))
    print("  ]\n}")
