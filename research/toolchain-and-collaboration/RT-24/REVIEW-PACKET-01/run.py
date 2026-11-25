"""Render exact review packets from the committed source/typed-diff fixture."""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import platform
import runpy
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BASELINE = "cd4d59dcd8b698e54d5a081b7e31ea958c8f6f03"
UPSTREAM = HERE.parent / "DIFF-OBSERVATION-LAYERS-01/run.py"
DATA = runpy.run_path(str(UPSTREAM))
VERSION = "closed-fixture-review/v1"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()


def assemble(work, fixture, name):
    row = fixture["cases"][name]
    git = DATA["git"]
    candidate = row["candidate"]
    pair = {
        "schema": VERSION, "base_commit": fixture["base_commit"], "base_tree": fixture["base_tree"],
        "candidate_commit": candidate,
        "candidate_tree": git(work, "rev-parse", candidate + "^{tree}").decode().strip(),
        "observation_inputs": DATA["INPUTS"],
    }
    raw = row["raw_patch"]
    before = fixture["base_snapshot"]
    semantic = {"state": "unavailable", "reason": row.get("admission_error")}
    if "snapshot" in row:
        after = row["snapshot"]
        semantic = {
            "state": "checked", "before_root": before["semantic_root"],
            "after_root": after["semantic_root"], "selection_changes": row["changed_slots"],
            "before_provider": before["compute_provider"], "after_provider": after["compute_provider"],
            "before_observations": before["observations"], "after_observations": after["observations"],
        }
    packet = {"subject": pair, "patch_sha256": digest(raw.encode()), "source_patch": raw,
              "semantic": semantic}
    return packet | {"packet_digest": digest(canonical(packet))}


def render(name, packet):
    subject = packet["subject"]
    semantic = packet["semantic"]
    lines = [f"# Review bundle for {name.replace('-', ' ')}", "",
             "## Revision pair", "",
             "| Role | Commit | Tree |", "| --- | --- | --- |",
             f"| Base | `{subject['base_commit']}` | `{subject['base_tree']}` |",
             f"| Candidate | `{subject['candidate_commit']}` | `{subject['candidate_tree']}` |",
             "", f"Review bundle SHA-256 `{packet['packet_digest']}`.", "",
             "## Semantic changes", ""]
    if semantic["state"] == "unavailable":
        lines += [f"Semantic comparison unavailable. {semantic['reason']}.",
                  "", "Interpreter observations unavailable for the candidate.", ""]
    else:
        lines += [
            f"Base semantic root `{semantic['before_root']}`.",
            f"Candidate semantic root `{semantic['after_root']}`.", "",
        ]
        if semantic["selection_changes"]:
            lines += ["| Changed slot | Before | After |", "| --- | --- | --- |"]
            for slot, change in semantic["selection_changes"].items():
                lines.append(f"| `{slot}` | `{change['before']}` | `{change['after']}` |")
            lines += [""]
        else:
            lines += ["No typed selection changes in the admitted fixture.", ""]
        if semantic["before_provider"] != semantic["after_provider"]:
            lines += [
                f"Previous exact provider `{semantic['before_provider']}`.",
                f"Selected exact provider `{semantic['after_provider']}`.", "",
            ]
        lines += ["## Bounded interpreter observations", "",
                  "| Input | Base result and trace | Candidate result and trace |",
                  "| ---: | --- | --- |"]
        for word, before, after in zip(subject["observation_inputs"], semantic["before_observations"],
                                       semantic["after_observations"], strict=True):
            lines.append(f"| {word} | `{json.dumps(before)}` | `{json.dumps(after)}` |")
        lines += [""]
    lines += ["## Exact source patch", "",
              f"Patch SHA-256 `{packet['patch_sha256']}`.", ""]
    if packet["source_patch"]:
        lines += ["````diff", packet["source_patch"].rstrip("\n"), "````", ""]
    else:
        lines += ["No Git tree byte changes.", ""]
    return "\n".join(lines)


def verify(work, fixture, name, packet):
    return assemble(work, fixture, name) == packet


def run(output_dir):
    summaries = {}
    with TemporaryDirectory(prefix="llmlang-review-packet-") as temp:
        work = Path(temp)
        fixture = DATA["run"](work)
        packets = {name: assemble(work, fixture, name) for name in fixture["cases"]}
        for name, packet in packets.items():
            checked = verify(work, fixture, name, packet)
            rendered = render(name, packet)
            semantic = packet["semantic"]
            assert checked and packet["packet_digest"] in rendered and packet["patch_sha256"] in rendered
            assert "Exact source patch" in rendered
            if semantic["state"] == "checked":
                assert "Bounded interpreter observations" in rendered
                assert semantic["after_root"] in rendered
            else:
                assert "Semantic comparison unavailable" in rendered
                assert "No typed selection changes" not in rendered
                assert "Bounded interpreter observations" not in rendered
            slot_names = list(semantic.get("selection_changes", {}))
            summaries[name] = {
                "state": semantic["state"], "has_source_patch": bool(packet["source_patch"]),
                "changed_slots": slot_names, "packet_digest": packet["packet_digest"],
                "render_sha256": digest(rendered.encode()), "exactly_verified": checked,
            }
            if name in {"retarget-provider", "invalid-provider"}:
                (output_dir / (name + ".md")).write_text(rendered, encoding="utf-8")
        chosen = packets["retarget-provider"]
        wrong_patch = chosen | {"source_patch": packets["source-format"]["source_patch"]}
        wrong_scope = deepcopy(chosen)
        wrong_scope["subject"]["observation_inputs"] = DATA["INPUTS"][:-1]
        wrong_scope["packet_digest"] = digest(canonical({
            key: value for key, value in wrong_scope.items() if key != "packet_digest"
        }))
        test_cases = {"wrong_patch": wrong_patch, "wrong_scope_with_new_digest": wrong_scope,
                      "wrong_candidate": packets["explicit-neutral-add"]}
        rejected = [name for name, packet in test_cases.items()
                    if not verify(work, fixture, "retarget-provider", packet)]
        assert rejected == list(test_cases)
        assert summaries["docs-only"]["changed_slots"] == []
        assert summaries["retarget-provider"]["changed_slots"] == ["binding:compute"]
        neutral = packets["explicit-neutral-add"]["semantic"]
        assert neutral["before_observations"] == neutral["after_observations"]
        assert neutral["before_root"] != neutral["after_root"]
    sources = {}
    for path in (UPSTREAM, *(
        ROOT / relative for relative in (
            "research/toolchain-and-collaboration/RT-24/COMMIT-TREE-SEMANTIC-ROOT-01/run.py",
            "research/PROTOTYPES/DEPENDENCY-GRAPH-01/src/semantic_graph.py",
            "research/PROTOTYPES/DEPENDENCY-GRAPH-01/src/recursive_identity.py",
            "research/PROTOTYPES/DEPENDENCY-GRAPH-01/src/spg_admission.py",
            "research/PROTOTYPES/DEPENDENCY-GRAPH-01/src/spg_representation.py",
        )
    )):
        relative = str(path.relative_to(ROOT))
        archived = subprocess.check_output(["git", "show", f"{BASELINE}:{relative}"], cwd=ROOT)
        assert path.read_bytes() == archived, relative
        sources[relative] = digest(archived)
    return {
        "baseline": BASELINE, "git": subprocess.check_output(["git", "--version"], text=True).strip(),
        "python": platform.python_version(), "runner_sha256": digest(Path(__file__).read_bytes()),
        "source_sha256": sources, "bundle_summaries": summaries, "refused_controls": rejected,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output_dir), indent=2))
