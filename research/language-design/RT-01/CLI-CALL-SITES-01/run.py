#!/usr/bin/env python3
"""Compare caller preservation policies on native Calculator programs and exact Git trees."""

from collections import Counter
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import importlib.util
from itertools import product
import json
from pathlib import Path
import platform
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
TYPED = HERE.parent / "TYPED-CLI-01"
sys.path.insert(0, str(TYPED))
spec = importlib.util.spec_from_file_location("typed_cli_fixture", TYPED / "run.py")
typed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(typed)
from src.semantic_graph import ContentStore, make_snapshot
from tests import test_rt24_merge_tree_gate as git_fixture

EXPORTS = "program/selection.json"
ORIGINAL = "program/division.json"
MOVED = "program/legacy/division.json"
NEW = "program/report/division.json"
CLIENTS = ("script", "report")
POLICIES = ("filesystem_path", "current_alias", "keep_previous_pin", "exact_calls", "warm_exact_calls")
BACKENDS = ("files", "reftable")
PHASES = ("baseline", "move", "split", "dropped_legacy")
FLOOR_CASES = {"T-0003-05", "RT-01-calc-eof"}


def checksum(data):
    return sha256(data).hexdigest()


def git(repo, *args):
    return git_fixture.git(repo, *args).decode().strip()


def read(repo, revision, path):
    return json.loads(git_fixture.git(repo, "show", f"{revision}:{path}"))


def admit(store, contract, recipe):
    _, admitted = typed.model.admit(recipe)
    body = {"identity": contract, "entry": admitted.mapping["calculator"], "recipe": recipe}
    return store.put("rt01-calculator-provider-v1", body)


def history(repo, backend, baseline, floor):
    git(repo, "init", "--quiet", "--template=", "--initial-branch=base", "--object-format=sha1",
        f"--ref-format={backend}")
    assert git(repo, "rev-parse", "--show-ref-format") == backend
    old = {"contract": "truncating", "definition": baseline}
    new = {"contract": "floor", "definition": floor}
    source = {"paths": {"legacy": ORIGINAL}, "alias": "legacy"}
    initial = git_fixture.commit(repo, {ORIGINAL: old, EXPORTS: source})
    moved = git_fixture.commit(repo, {ORIGINAL: None, MOVED: old,
                                     EXPORTS: {"paths": {"legacy": MOVED}, "alias": "legacy"}})
    split = git_fixture.commit(repo, {NEW: new, EXPORTS: {"paths": {"legacy": MOVED, "floor": NEW},
                                                          "alias": "floor"}})
    dropped = git_fixture.commit(repo, {MOVED: None, EXPORTS: {"paths": {"floor": NEW}, "alias": "floor"}})
    return dict(zip(PHASES, (initial, moved, split, dropped)))


def reconstructed(repo, revision):
    store = ContentStore()
    inventory = read(repo, revision, EXPORTS)
    paths = inventory["paths"]
    names = set(git(repo, "ls-tree", "-r", "--name-only", revision).splitlines())
    assert set(paths.values()) | {EXPORTS} == names
    locations = {}
    providers = {}
    for name, path in paths.items():
        declaration = read(repo, revision, path)
        identity = admit(store, declaration["contract"], declaration["definition"])
        providers[name] = identity
        locations[path] = identity
    selection = store.put("rt01-calculator-alias-v1", {"role": inventory["alias"]})
    snapshot = make_snapshot({**providers, "public_alias": selection})
    return {"revision": revision, "tree": git(repo, "rev-parse", f"{revision}^{{tree}}"),
            "root": snapshot.root_hash, "providers": providers, "locations": locations,
            "alias": providers[inventory["alias"]]}


def build_native(directory, sem_store, archive):
    baseline_cases = [case for case in typed.acceptance.CASES if case.program == "calculator"]
    floor_cases = [replace(case, stdout=b"-4\n") if case.identifier in FLOOR_CASES else case
                   for case in baseline_cases]
    inputs = {"truncating": baseline_cases, "floor": floor_cases}
    runtime = (TYPED / "runtime.rs").read_text()
    matrix = {}
    for contract, address in archive.items():
        body = sem_store.get(address).payload
        store, snapshot = typed.model.admit(body["recipe"])
        assert snapshot.mapping["calculator"] == body["entry"]
        native_source = typed.emit(typed.model.body_for(store, snapshot, "calculator"), address, runtime)
        for optimize in (0, 3):
            binary, identity = typed.compile_rust(directory, f"{contract}_{optimize}", native_source, optimize)
            matrix[contract, optimize] = {
                "build": identity, "provider": address,
                "results": {claim: [typed.observe(binary, case) for case in cases]
                            for claim, cases in inputs.items()},
            }
        assert matrix[contract, 0]["results"] == matrix[contract, 3]["results"]
        assert all(row["matches"] for row in matrix[contract, 0]["results"][contract])
    return matrix


def binding(policy, inventory, expected, previous, store):
    if policy == "filesystem_path":
        return inventory["locations"].get(ORIGINAL)
    if policy == "current_alias":
        return inventory["alias"]
    if policy == "keep_previous_pin":
        return previous if previous in inventory["providers"].values() else None
    if policy == "warm_exact_calls":
        return expected if store.get(expected) else None
    return expected if expected in inventory["providers"].values() else None


def assess(phase, state, policy, previous, archive, store, physical):
    out = {}
    for client in CLIENTS:
        wanted = "floor" if client == "report" and phase in {"split", "dropped_legacy"} else "truncating"
        required = archive[wanted]
        selected = binding(policy, state, required, previous, store)
        result = {
            "required_contract": wanted, "required_provider": required, "selected_provider": selected,
            "missing_from_tree": selected is not None and selected not in state["providers"].values(),
            "missing_selection": selected is None,
        }
        if selected:
            actual = store.get(selected).payload["identity"]
            receipt = physical[actual, 3]
            assert selected == receipt["provider"]
            failures = [row["case"] for row in receipt["results"][wanted] if not row["matches"]]
            result["wrong_cases"] = failures
            result["native_matches"] = not failures
        else:
            result["wrong_cases"] = []
            result["native_matches"] = False
        out[client] = result
    native_matches = all(row["native_matches"] for row in out.values())
    eligible = native_matches and not any(row["missing_from_tree"] for row in out.values())
    return {"clients": out, "native_matches_without_inventory": native_matches, "eligible": eligible}


def run(directory):
    version = subprocess.check_output(["git", "--version"], text=True).strip()
    assert version == "git version 2.52.0", version
    baseline = json.loads((TYPED / "programs.json").read_bytes())
    floor = deepcopy(baseline)
    floor["calculator"]["division"] = "floor"
    borrowed = ContentStore()
    archive = {"truncating": admit(borrowed, "truncating", baseline), "floor": admit(borrowed, "floor", floor)}
    physical = build_native(directory, borrowed, archive)
    experiments = {}
    for backend in BACKENDS:
        repo = directory / backend
        repo.mkdir()
        revisions = history(repo, backend, baseline, floor)
        choices = {phase: reconstructed(repo, revision) for phase, revision in revisions.items()}
        assert choices["baseline"]["root"] == choices["move"]["root"]
        assert choices["baseline"]["tree"] != choices["move"]["tree"]
        assert len({choices[key]["root"] for key in ("baseline", "split", "dropped_legacy")}) == 3
        experiments[backend] = {
            phase: {"state": choices[phase], "policies": {
                policy: assess(phase, choices[phase], policy, archive["truncating"], archive, borrowed, physical)
                for policy in POLICIES
            }} for phase in PHASES
        }
    assert experiments["files"] == experiments["reftable"]
    matrix = experiments["files"]
    assert all(matrix[phase]["policies"]["exact_calls"]["eligible"] for phase in PHASES[:-1])
    assert not matrix["dropped_legacy"]["policies"]["exact_calls"]["eligible"]
    assert matrix["dropped_legacy"]["policies"]["warm_exact_calls"]["clients"]["script"]["native_matches"]
    assert matrix["dropped_legacy"]["policies"]["warm_exact_calls"]["clients"]["script"]["missing_from_tree"]
    assert set(matrix["split"]["policies"]["current_alias"]["clients"]["script"]["wrong_cases"]) == FLOOR_CASES
    assert set(matrix["split"]["policies"]["keep_previous_pin"]["clients"]["report"]["wrong_cases"]) == FLOOR_CASES
    metrics = {}
    for policy in POLICIES:
        totals = Counter()
        for backend in BACKENDS:
            for phase in PHASES:
                selected = experiments[backend][phase]["policies"][policy]
                totals["eligible"] += selected["eligible"]
                totals["native_only_claims"] += selected["native_matches_without_inventory"]
                for client in selected["clients"].values():
                    totals["missing_choices"] += client["missing_selection"]
                    totals["outside_inventory"] += client["missing_from_tree"]
                    totals["disagreements"] += len(client["wrong_cases"])
        metrics[policy] = dict(totals)
    return {
        "schema": "llmlang-rt01-cli-call-sites/1", "python": platform.python_version(),
        "git": version,
        "rustc": subprocess.check_output(["rustc", "-Vv"], text=True).splitlines(),
        "runner_sha256": checksum(Path(__file__).read_bytes()),
        "prerequisite_hashes": {name: checksum((TYPED / name).read_bytes())
                                for name in ("run.py", "model.py", "runtime.rs", "programs.json")},
        "native_observations": sum(len(cases) for row in physical.values() for cases in row["results"].values()),
        "distinct_native_vectors": sum(len(row["results"]["truncating"]) for row in physical.values()),
        "native_route_profiles": len(physical), "git_candidates": len(BACKENDS) * len(PHASES), "metrics": metrics,
        "native": {f"{name}_O{level}": evidence for (name, level), evidence in physical.items()},
        "histories": experiments,
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-cli-sites-") as scratch:
        result = run(Path(scratch))
    native = result.pop("native")
    histories = result.pop("histories")
    print(json.dumps(result, indent=2).removesuffix("\n}") + ',\n  "native": {')
    print(",\n".join(f"    {json.dumps(name)}: {json.dumps(row)}" for name, row in native.items()))
    print('  },\n  "histories": {')
    print(",\n".join(f"    {json.dumps(name)}: {json.dumps(row)}" for name, row in histories.items()))
    print("  }\n}")
