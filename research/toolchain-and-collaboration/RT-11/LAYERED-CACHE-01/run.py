#!/usr/bin/env python3
"""Test independent action metadata and artifact acquisition across cache layers."""

from collections import Counter
from dataclasses import dataclass, field
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import platform
import sys

HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.parent / "CACHE-INDEX-MERGE-01"
sys.path.insert(0, str(PREVIOUS))
spec = spec_from_file_location("layered_cache_controls", PREVIOUS / "run.py")
prior = module_from_spec(spec)
spec.loader.exec_module(prior)

ACTION = prior.record()["action_key"]
FIRST = prior.FIRST
SECOND = prior.SECOND
AUTHORITIES = {"builder-a", "builder-b"}
EVIDENCE = "review-v1"


@dataclass
class Layer:
    name: str
    records: tuple = ()
    blobs: dict = field(default_factory=dict)
    reachable: bool = True


@dataclass
class LayeredArtifacts:
    layers: list
    payloads: dict = field(default_factory=dict)
    locations: dict = field(default_factory=dict)
    corrupt_copies: list = field(default_factory=list)

    def get(self, identity):
        corrupt = None
        for layer in self.layers:
            payload = layer.blobs.get(identity) if layer.reachable else None
            if payload is None:
                continue
            if prior.artifact_id(payload) == identity:
                self.payloads[identity] = payload
                self.locations[identity] = layer.name
                return payload
            self.corrupt_copies.append((identity, layer.name))
            corrupt = payload
        return corrupt


def candidates(*indexes):
    return prior.merge(indexes, prior.COMPONENTS)[ACTION]


def locate(layers, manifest, *, authorities=AUTHORITIES, evidence=EVIDENCE):
    if manifest is None:
        return {"status": "view-unavailable"}
    visible = {item.identity: item for layer in layers if layer.reachable for item in layer.records}
    missing = set(manifest) - visible.keys()
    if missing:
        return {"status": "records-unavailable", "missing": sorted(missing)}
    records = tuple(visible[identity] for identity in sorted(manifest))
    artifacts = LayeredArtifacts(layers)
    status, decision = prior.lookup(
        {ACTION: records} if records else {}, ACTION, required_evidence=evidence,
        authorities=authorities, verified=set(manifest), artifacts=artifacts, required_outputs=1,
    )
    result = {"status": status, "corrupt_copies": sorted(artifacts.corrupt_copies)}
    if decision is not None:
        result["artifacts"] = [(identity, artifacts.locations[identity]) for identity in decision[1]]
        result["original_records"] = [item.identity for item in records]
        local = layers[0]
        local.records = tuple({item.identity: item for item in (*local.records, *records)}.values())
        local.blobs.update({identity: artifacts.payloads[identity] for identity in decision[1]})
    return result


def layers(*, process=(), workspace=(), team=(), global_blobs=None, process_blobs=None,
           workspace_blobs=None, team_blobs=None, remote_available=True):
    return [Layer("process", process, dict(process_blobs or {})),
            Layer("workspace", workspace, dict(workspace_blobs or {})),
            Layer("team", team, dict(team_blobs or {}), remote_available),
            Layer("global-content", (), dict(global_blobs or {}))]


def results():
    a, = candidates(prior.index("builder-a"))
    b, = candidates(prior.index("builder-b"))
    other, = candidates(prior.index("builder-b", EVIDENCE, prior.record(output_artifacts=[SECOND])))
    good = {FIRST: prior.PAYLOAD}
    seen = []

    def check(label, layer_set, known, status, source=None, **policy):
        manifest = None if known is None else tuple(item.identity for item in known)
        actual = locate(layer_set, manifest, **policy)
        expected_artifacts = None if source is None else [(FIRST, source)]
        if actual["status"] != status or actual.get("artifacts") != expected_artifacts:
            raise AssertionError(f"{label}: {actual}")
        seen.append({"case": label, "result": actual})

    check("process exact record and payload", layers(process=(a,), process_blobs=good), (a,), "hit", "process")
    check("workspace hit after process miss", layers(workspace=(a,), workspace_blobs=good), (a,), "hit", "workspace")
    check("team hit after nearer misses", layers(team=(a,), team_blobs=good), (a,), "hit", "team")
    check("workspace record with evicted payload", layers(workspace=(a,), global_blobs=good), (a,), "hit", "global-content")
    check("global bytes without an action record", layers(global_blobs=good), (), "miss")
    check("unauthenticated view unknown despite local bytes", layers(process=(a,), process_blobs=good),
          None, "view-unavailable")
    check("evicted output retains metadata", layers(workspace=(a,)), (a,), "artifact-missing")
    check("corrupt nearer copy falls back to verified lower copy",
          layers(process=(a,), process_blobs={FIRST: prior.OTHER}, global_blobs=good), (a,), "hit", "global-content")
    check("corrupt sole copy", layers(process=(a,), process_blobs={FIRST: prior.OTHER}), (a,), "artifact-integrity-error")
    check("authorized cross-layer disagreement survives eviction", layers(process=(a,), team=(other,), process_blobs=good),
          (a, other), "conflict")
    check("disagreement outside authority does not win", layers(process=(a,), team=(other,), process_blobs=good),
          (a, other), "hit", "process", authorities={"builder-a"})
    check("unreachable team record keeps pinned view incomplete",
          layers(process=(a,), process_blobs=good, team=(b,), remote_available=False), (a, b), "records-unavailable")
    check("mirrored team record completes the view offline",
          layers(process=(a,), process_blobs=good, workspace=(b,), team=(b,), remote_available=False),
          (a, b), "hit", "process")
    promotion = layers(team=(a, b), global_blobs=good)
    check("promote checked records and bytes into process", promotion, (a, b), "hit", "global-content")
    promotion[2].reachable = False
    promotion[3].blobs.clear()
    check("promoted process hit offline", promotion, (a, b), "hit", "process")
    check("promotion retains original authority after revocation", promotion, (a, b), "no-applicable-attestation",
          authorities=set())
    check("changed evidence scope is checked on promoted data", promotion, (a, b), "no-applicable-attestation",
          evidence="review-v2")
    assert {item.producer for item in promotion[0].records} == AUTHORITIES
    early_status, _ = prior.lookup(
        {ACTION: (a,)}, ACTION, required_evidence=EVIDENCE, authorities=AUTHORITIES,
        verified={a.identity}, artifacts=good, required_outputs=1,
    )
    if early_status != "hit":
        raise AssertionError("Expected process-only admission to hide the shared view differences")
    return {
        "schema": "llmlang-layered-cache/1", "python": platform.python_version(), "action_key": ACTION,
        "sources_sha256": {name: sha256(path.read_bytes()).hexdigest() for name, path in {
            "runner": Path(__file__), "cache_index": prior.PACKAGE / "cache_index.py",
            "merge": PREVIOUS / "merge.py", "fixture": PREVIOUS / "run.py",
        }.items()},
        "first_layer_control": early_status, "cases": seen, "counts": dict(Counter(item["result"]["status"] for item in seen)),
    }


if __name__ == "__main__":
    print(json.dumps(results(), indent=2))
