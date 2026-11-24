"""Check closed, reviewed semantic prefixes of real temporary Git histories."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from tests import test_rt24_merge_tree_gate as tree
from src.semantic_dependency_index import publish_declaration
from src.semantic_graph import ContentStore, digest


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def git_text(repo, *args):
    return tree.git(repo, *args).decode("utf-8").strip()


def stage(repo, **parts):
    paths = {"callee": tree.CALLEE, "caller": tree.CALLER}
    return tree.commit(repo, {paths[key]: value for key, value in parts.items()})


def history(repo):
    tree.git(repo, "init", "--quiet", "--template=", "--initial-branch=base", "--object-format=sha1")
    store = ContentStore()
    contract = tree.declaration("contract", "contract:score", {"result": "Int"})
    contract_hash = publish_declaration(store, contract)

    def declaration(offset):
        return tree.declaration("function", "function:score", {"offset": offset}, references=[{
            "reference_id": "provides", "relation": "provides_contract",
            "target_hash": contract_hash, "target_kind": "contract",
        }])

    old, intended, wrong = (declaration(offset) for offset in (1, 2, 99))
    old_hash, intended_hash, wrong_hash = (publish_declaration(store, value) for value in (old, intended, wrong))

    def caller(provider_hash):
        return tree.declaration("function", "function:entry", call_sites=[{
            "call_site_id": "invoke", "targets": [{
                "target_id": "direct", "target_hash": provider_hash,
                "required_contract_hash": contract_hash, "condition": "entry-active",
            }],
        }])

    caller_old = [tree.row("caller", caller(old_hash))]
    caller_new = [tree.row("caller", caller(intended_hash))]
    providers_new = [tree.row("callee", intended)]
    old_retained = tree.row("callee.retained", old)
    base = tree.commit(repo, {
        tree.MANIFEST: tree.manifest(tree.CONTRACT, tree.CALLEE, tree.CALLER),
        tree.CONTRACT: [tree.row("contract", contract)], tree.CALLEE: [tree.row("callee", old)],
        tree.CALLER: caller_old, "notes.txt": "baseline notes\n",
    })
    tree.git(repo, "switch", "--quiet", "-c", "target", base)
    onto = tree.commit(repo, {"notes.txt": "destination notes\n"})

    tree.git(repo, "switch", "--quiet", "-c", "drop-then-migrate", base)
    broken = stage(repo, callee=providers_new)
    closed = stage(repo, caller=caller_new)

    tree.git(repo, "switch", "--quiet", "-c", "retain-migrate-remove", base)
    retained = stage(repo, callee=[*providers_new, old_retained])
    migrated = stage(repo, caller=caller_new)
    approved = stage(repo, callee=providers_new)

    tree.git(repo, "switch", "--quiet", "-c", "different-prefix", base)
    wrong_step = stage(repo, callee=[tree.row("callee", wrong), old_retained])
    corrected = stage(repo, callee=[*providers_new, old_retained], caller=caller_new)
    same_terminal = stage(repo, callee=providers_new)

    return base, onto, {
        "invalid_prefix": (broken, closed),
        "approved_prefixes": (retained, migrated, approved),
        "different_valid_prefix": (wrong_step, corrected, same_terminal),
    }, (old_hash, intended_hash, wrong_hash)


def observe(repo, commit):
    inventory = tree.read_inventory(repo, commit)
    info = {"commit": commit, "parent": git_text(repo, "show", "-s", "--format=%P", commit),
            "tree": inventory.tree}
    try:
        _, snapshot = tree.import_closed(inventory)
    except tree.GraphImportError as error:
        return {**info, "status": "unclosed", "diagnostic": str(error)}
    sites = inventory.declarations["caller"]["call_sites"]
    exact_target = sites[0]["targets"][0]["target_hash"]
    return {**info, "status": "closed", "root": snapshot.root_hash,
            "target": exact_target, "callee": snapshot.mapping["callee"],
            "retained": snapshot.mapping.get("callee.retained")}


def span(repo, start, end):
    commits = git_text(repo, "rev-list", "--reverse", f"{start}..{end}").splitlines()
    require(bool(commits), "Expected a nonempty linear sequence")
    parents = [git_text(repo, "show", "-s", "--format=%P", commit) for commit in commits]
    require(parents == [start, *commits[:-1]], "The candidate is not one exact linear history")
    return commits


def replay(repo, method, base, onto, original):
    if method == "rebase":
        tree.git(repo, "switch", "--quiet", "--detach", original[-1])
        tree.git(repo, "rebase", "--onto", onto, base)
    else:
        tree.git(repo, "switch", "--quiet", "--detach", onto)
        if method == "cherry-pick":
            tree.git(repo, "cherry-pick", *original)
        else:
            tree.git(repo, "merge", "--squash", original[-1])
            tree.git(repo, "commit", "--quiet", "-m", "finite net effect")
    require(tree.git(repo, "status", "--porcelain") == b"", "Git replay did not finish cleanly")
    return span(repo, onto, git_text(repo, "rev-parse", "HEAD"))


def verify():
    version = subprocess.check_output(["git", "--version"], text=True).strip()
    require(version == "git version 2.52.0", version)
    with TemporaryDirectory(prefix="llmlang-replay-stages-") as directory:
        repo = Path(directory)
        base, onto, cases, (old_hash, intended_hash, wrong_hash) = history(repo)
        approved = [observe(repo, commit) for commit in cases["approved_prefixes"]]
        reference_roots = [entry["root"] for entry in approved]
        require([entry["retained"] for entry in approved] == [old_hash, old_hash, None],
                "Approved call migration must retain the old provider until it is no longer selected")
        require([entry["target"] for entry in approved] == [old_hash, intended_hash, intended_hash],
                "Planned call-site targets differ")
        require(all(entry["callee"] == intended_hash for entry in approved),
                "The approved prefixes must use the intended new provider")
        exact_terminal = reference_roots[-1]

        missing = observe(repo, cases["invalid_prefix"][0])
        require(missing["status"] == "unclosed" and old_hash in missing["diagnostic"],
                "Invalid control did not require the old provider")
        warm, _ = tree.import_closed(tree.read_inventory(repo, base))
        warmed = tree.publish_rows(tree.read_inventory(repo, missing["commit"]).declarations, warm)
        require(tree.audit_candidate_snapshot_graph(warm, warmed).valid and old_hash not in warmed.mapping.values(),
                "Warm-cache control did not reproduce the source closure hazard")
        wrong = observe(repo, cases["different_valid_prefix"][0])
        require(wrong["callee"] == wrong_hash and wrong["target"] == old_hash and wrong["root"] != reference_roots[0],
                "Closed alternate prefix must differ from the approved state")

        experiments = {}
        final_trees = set()
        for case, original in cases.items():
            require(span(repo, base, original[-1]) == list(original), "Captured source chain changed")
            for method in ("rebase", "cherry-pick", "squash"):
                commits = replay(repo, method, base, onto, original)
                steps = [observe(repo, commit) for commit in commits]
                terminal = steps[-1]
                require(terminal["root"] == exact_terminal and terminal["target"] == intended_hash,
                        "The selected net change or final call site differed")
                require(tree.git(repo, "show", f"{terminal['commit']}:notes.txt") == b"destination notes\n",
                        "Replay lost approved ordinary destination content")
                final_trees.add(terminal["tree"])
                closed = all(step["status"] == "closed" for step in steps)
                same_prefixes = method != "squash" and [step.get("root") for step in steps] == reference_roots
                require(len(steps) == (1 if method == "squash" else len(original)), "Unexpected replay length")
                require(closed == (method == "squash" or case != "invalid_prefix"), "Wrong prefix closure result")
                require(same_prefixes == (method != "squash" and case == "approved_prefixes"),
                        "Wrong ordered approval result")
                record = {"source_commits": original, "source_parent": base, "onto": onto,
                          "replayed": steps, "terminal_semantic_gate": True,
                          "all_replayed_commits_closed": closed,
                          "preserves_approved_semantic_prefixes": same_prefixes}
                experiments[f"{case}/{method}"] = {**record, "evidence": digest((case, method, record))}
        require(len(final_trees) == 1, "The three candidate policies did not produce one exact terminal tree")
        return {"git": version, "terminal_tree": final_trees.pop(), "terminal_root": exact_terminal,
                "approved_prefix_roots": reference_roots, "warm_store_masks_unclosed_prefix": True,
                "experiments": experiments}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(verify(), sort_keys=True, indent=2) + "\n")
