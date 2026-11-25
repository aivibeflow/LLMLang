"""Verify normalized candidate profile coverage and exact archived study inputs."""

from hashlib import sha256
import json
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent


def run():
    manifest = (HERE / "profiles.json").read_bytes()
    data = json.loads(manifest)
    dimensions = data["dimensions"]
    profiles = data["profiles"]
    assert data["adopted_profile"] is None
    assert set(profiles) == {"A", "B", "C", "D"} and len(set(dimensions)) == len(dimensions) == 9
    evidence = set()
    for profile in profiles.values():
        assert len(profile["vector"]) == len(dimensions)
        assert all(isinstance(coordinate, str) and coordinate for coordinate in profile["vector"])
        assert len(set(profile["checks"])) == 2 and profile["open"]
        evidence.update(profile["checks"])
    evidence.add("research/language-design/RT-03/CORE-LANGUAGE-SEMANTICS.md")
    pinned = {}
    for path in sorted(evidence):
        archive = subprocess.check_output(["git", "show", f"{data['baseline']}:{path}"])
        pinned[path] = sha256(archive).hexdigest()
    return {
        "baseline": data["baseline"], "manifest_sha256": sha256(manifest).hexdigest(),
        "profiles": len(profiles), "coordinates": len(profiles) * len(dimensions),
        "pinned_report_sha256": pinned,
        "adopted_profile": data["adopted_profile"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, indent=2))
