#!/usr/bin/env python3
"""Census of observation ledgers and explicitly bound inputs on a pinned tree."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import PurePosixPath
import re
import subprocess


BASE = "356ddee8964a8b0bb49457e5252fdec7e8b12f83"
RELEASE = "research/language-design/RT-02"
FFI = "research/compiler-and-translation/RT-13"
QUALITY = "research/quality-audit"
GIT = "research/toolchain-and-collaboration/RT-19"
TOOLS = "research/formal-verification/RT-33"
BOOTSTRAP = "research/toolchain-and-collaboration/RT-21"
TCP = "research/runtime-and-systems/RT-26"
LOGOS = "research/PROTOTYPES/DEPENDENCY-GRAPH-01/logos_binding"

# Field paths are selected from the producer schema. Capability, outcome and
# target profiles do not imply the version or identity of the executing host.
EVIDENCE = {
    "logos-verdict": ("logos_revision runtime_lean_revision verification_lean_revision mathlib_revision", ""),
    "FFI-AGGREGATE-CROSS-ABI-01": ("tool_versions", ""),
    "FFI-CALLBACK-LIFETIME-01": ("versions.c versions.libc versions.python versions.rust", "versions.machine"),
    "FFI-CROSS-BUILD-CACHE-01": ("tool_identity", ""),
    "FFI-HEADER-IMPORT-01": ("tool_versions headers_sha256 libraries_sha256", ""),
    "FFI-LOADER-SCOPE-01": ("versions.binutils versions.gcc versions.glibc", "versions.machine"),
    "FFI-MANAGED-CALLBACK-01": ("versions", ""),
    "FFI-VARIADIC-ABI-01": ("tools", ""),
    "TEMPORAL-ADAPTER-01": ("", ""),
    "WHY3-BOOGIE-ADAPTER-01": ("versions", ""),
    "RELEASE-REQUIREMENT-01": ("proof.version proof.checker_sha256", ""),
    "2026-11-23-historical-rerun-observations.json": ("python", "runner"),
    "2026-11-23-pinned-lean-proof-observations.json": ("lean_version lean_commit lean_target", ""),
    "2026-11-23-root-census-observations.json": ("", ""),
    "TCP-TRANSPORT-ACCOUNTING-01": ("compiler libc linux_tcp_header_sha256", "kernel"),
    "COHERENT-MULTIREF-01": ("git", ""),
    "GIT-REF-FAULTS-01": ("git", ""),
    "PUBLICATION-CONTRACT-01": ("jar_sha256", ""),
    "TWO-REMOTE-PUBLICATION-01": ("git sqlite", ""),
    "DEPENDENCY-BOOTSTRAP-01": ("compiler", ""),
}


def git(*args):
    return subprocess.check_output(["git", *args])


def blob_at(revision, path):
    return git("rev-parse", "--verify", f"{revision}:{path}").decode().strip()


def digest(payload):
    return sha256(payload).hexdigest()


def field(data, name):
    for key in name.split("."):
        data = data[key]
    return data


def recorded_fields(data, names):
    values = {}
    for name in names.split():
        value = field(data, name)
        assert value, name
        if isinstance(value, dict):
            values[name] = sorted(value)
        else:
            values[name] = value
    return values


def bound(data, field_name, path, revision=BASE, algorithm="sha256"):
    claimed = field(data, field_name)
    blob = blob_at(revision, path)
    observed = digest(git("cat-file", "blob", blob)) if algorithm == "sha256" else blob
    assert claimed == observed, (field_name, revision, path, claimed, observed)
    return {"field": field_name, "blob": blob, "algorithm": algorithm,
            "value": observed, "path": path, "revision": revision}


def identities(path, data):
    directory = path.parent.as_posix()
    name = path.parent.name
    bindings = {
        "FFI-MANAGED-CALLBACK-01": [("prior_ledger_sha256", f"{FFI}/FFI-CALLBACK-LIFETIME-01/observations.json")],
        "RELEASE-REQUIREMENT-01": [("source_sha256", f"{directory}/requirements.txt"),
                                   ("oracle_sha256", f"{directory}/oracle.py"),
                                   ("proof.formalization_sha256", f"{directory}/Release.lean"),
                                   ("receipt.formalization_sha256", f"{directory}/Release.lean")],
        "TCP-TRANSPORT-ACCOUNTING-01": [("source_sha256", f"{directory}/probe.c")],
        "PUBLICATION-CONTRACT-01": [("model_sha256", f"{directory}/Publication.tla")],
        "DEPENDENCY-BOOTSTRAP-01": [("source_sha256", f"{directory}/dependency-tool.json"),
                                    ("profile_implementation_sha256", f"{directory}/fragment.py")],
    }
    results = [bound(data, key, source) for key, source in bindings.get(name, [])]
    if name == "FFI-HEADER-IMPORT-01":
        result = bound({"header": data["headers_sha256"]["fixture/input.c"]}, "header", f"{directory}/input.c")
        results.append({**result, "field": "headers_sha256[fixture/input.c]"})
    if name == "DEPENDENCY-BOOTSTRAP-01":
        results.append(bound(data, "register_projections.register_sha256",
                             "research/research-management/RESEARCH-DEPENDENCY-MAP.md",
                             data["register_projections"]["revision"]))
    if path.name == "2026-11-23-pinned-lean-proof-observations.json":
        revision = data["source_git_commit"]
        results.extend([bound(data, "source_sha256", data["source_path"], revision),
                        bound(data, "source_git_blob", data["source_path"], revision, "git-blob"),
                        bound(data, "toolchain_config_git_blob", f"{LOGOS}/lean-toolchain",
                              revision, "git-blob")])
    return results


def historical(path, data):
    if path.name == "2026-11-23-root-census-observations.json":
        revision = data["baseline_commit"]
        return [bound(entry, "blob", entry["path"], revision, "git-blob") for entry in data["review_queue"]]
    if path.name == "2026-11-23-historical-rerun-observations.json":
        commits = sorted({case["commit"] for case in data["cases"]})
        assert all(git("cat-file", "-t", item).strip() == b"commit" for item in commits)
        manifest = data["source_snapshot_manifest"]
        return {"available_commits": commits, "manifest": manifest, "manifest_blob": blob_at(BASE, manifest)}
    return None


def reports(files, path):
    if path.parent.as_posix() == QUALITY:
        return []
    if path.parent.name == "logos-verdict":
        candidates = ["research/formal-verification/RT-07/RT-07-LOGOS-CHECKER-TRUST-BOUNDARY.md"]
    else:
        parent = path.parent.parent.as_posix()
        candidates = [name for name in files if name.startswith(parent + "/") and
                      PurePosixPath(name).parent.as_posix() == parent and name.endswith(".md")]
    # Restrict to a literal Markdown link to the observations, or a reproduction
    # command which assigns the fixture path and names its observation output.
    needle = path.parent.name + "/" + path.name
    related = []
    for candidate in candidates:
        text = git("cat-file", "blob", files[candidate]).decode()
        if needle in text or (path.parent.name in text and "$study/observations.json" in text):
            related.append({"path": candidate, "blob": files[candidate]})
    return related


def main():
    files = {}
    for entry in git("ls-tree", "-r", "-z", BASE, "research").split(b"\0"):
        if entry:
            metadata, path = entry.decode().split("\t", 1)
            files[path] = metadata.split()[2]
    rows = []
    for filename, blob in sorted(files.items()):
        if not re.search(r"(^|[/.-])observations\.json$", filename):
            continue
        path = PurePosixPath(filename)
        data = json.loads(git("cat-file", "blob", blob))
        label = path.name if path.parent.as_posix() == QUALITY else path.parent.name
        tool_names, host_names = EVIDENCE[label]
        runner = str(path.parent / "run.py")
        rows.append({"path": filename, "blob": blob, "label": label,
                     "tool_fields": recorded_fields(data, tool_names), "host_fields": recorded_fields(data, host_names),
                     "adjacent_runner_blob": files.get(runner), "tracked_bindings": identities(path, data),
                     "historical_records": historical(path, data), "related_reports": reports(files, path)})
    assert {row["label"] for row in rows} == set(EVIDENCE) and len(rows) == len(EVIDENCE)
    summary = Counter({"ledgers": len(rows)})
    for row in rows:
        for metric in ("tool_fields", "host_fields", "adjacent_runner_blob", "related_reports"):
            summary[metric] += bool(row[metric])
        summary["direct_tracked_bindings"] += len(row["tracked_bindings"])
        if isinstance(row["historical_records"], list):
            summary["historical_queue_blob_matches"] += len(row["historical_records"])
    print(json.dumps({"baseline": BASE, "summary": summary, "rows": rows}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
