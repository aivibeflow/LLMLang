"""Compare guarded dispatch identities for scoped execution-cache reuse."""
import argparse
from dataclasses import dataclass
from itertools import product
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"))
from src.semantic_graph import ContentStore, digest, make_snapshot
from tests.test_rt24_merge_tree_gate import commit, git

FLAGS = (0, 1, 2, 3)
PROVIDERS = ("left", "right")
BASE = {"left": (3, 7), "right": (9, 11), "unrelated": (11, 19)}
EDITS = {
    "unchanged": BASE,
    "left-value": {**BASE, "left": (3, 8)},
    "right-value": {**BASE, "right": (9, 12)},
    "unrelated": {**BASE, "unrelated": (11, 20)},
    "left-equivalent": {**BASE, "left": (4, 6)},
}
MODES = ("whole-snapshot", "one-trace", "target-set", "exact-selector", "scoped-relation")
PROFILE = "rt05-finite-guarded-dispatch/1"


@dataclass(frozen=True)
class View:
    selector: str
    rows: tuple[str, ...]
    identities: dict[str, str]
    root: str


def source(mapping):
    return "".join(f"when {flags} call {provider}\n" for flags, provider in enumerate(mapping))


def read_selector(text):
    discovered = {}
    for line in text.splitlines():
        fields = line.split(" ")
        if len(fields) != 4:
            return None
        guard, flag, action, provider = fields
        if guard != "when" or action != "call" or flag not in {"0", "1", "2", "3"} or provider not in PROVIDERS:
            return None
        if int(flag) in discovered:
            return None
        discovered[int(flag)] = provider
    if discovered.keys() != set(FLAGS):
        return None
    return tuple(discovered[i] for i in FLAGS)


def build_view(text, providers):
    selector = read_selector(text)
    if selector is None:
        return None
    store = ContentStore()
    identities = {name: store.put("guarded-dispatch-provider", {"addends": operands})
                  for name, operands in providers.items()}
    address = store.put("guarded-dispatch-selector", {"format": PROFILE, "source": text})
    snapshot = make_snapshot({**identities, "dispatch": address})
    return View(address, selector, identities, snapshot.root_hash)


def keys(view, scope):
    relation = tuple((flags, view.rows[flags], view.identities[view.rows[flags]]) for flags in scope)
    targets = sorted({(provider, address) for _, provider, address in relation})
    payloads = (view.root, relation[0], targets, (view.selector, targets), relation)
    return {mode: digest([PROFILE, mode, scope, value]) for mode, value in zip(MODES, payloads, strict=True)}


def reference(mapping, stored, scope):
    # The oracle consumes the source generator's tables independently of the key extractor.
    observations = []
    for flags in scope:
        provider = mapping[flags]
        value = sum(stored[provider])
        observations.append((flags, ("emit", value), value))
    return tuple(observations)


def candidate_observations(view, catalog, scope):
    observations = []
    for flags in scope:
        left, right = catalog[view.rows[flags]]
        value = left + right
        observations.append((flags, ("emit", value), value))
    return tuple(observations)


def git_witness(witness):
    with TemporaryDirectory(prefix="llmlang-guarded-dispatch-") as tmp:
        repo = Path(tmp)
        git(repo, "init", "--quiet", "--template=", "--initial-branch=main", "--object-format=sha1")
        pins = []
        for name in ("before", "after"):
            value = witness[name]
            pins.append(commit(repo, {"selector.txt": value["source"],
                                      "providers.json": json.dumps(value["catalog"], sort_keys=True) + "\n"}))
        git(repo, "fsck", "--full")
        results = []
        for pin in pins:
            text = git(repo, "show", f"{pin}:selector.txt").decode()
            catalog = json.loads(git(repo, "show", f"{pin}:providers.json"))
            view = build_view(text, catalog)
            results.append({"commit": pin, "root": view.root, "keys": keys(view, witness["scope"]),
                            "outcome": candidate_observations(view, catalog, witness["scope"])})
        first, last = results
        assert first["keys"]["target-set"] == last["keys"]["target-set"]
        assert first["keys"]["scoped-relation"] != last["keys"]["scoped-relation"]
        assert first["outcome"] != last["outcome"]
        assert first["root"] != last["root"]
        return results


def example(initial, revised, scope, label):
    return {"scope": scope, "edit": label,
            "before": {"source": source(initial), "catalog": BASE},
            "after": {"source": source(revised), "catalog": EDITS[label]}}


def run():
    version = git(HERE, "--version").decode().strip()
    assert version == "git version 2.52.0"
    mappings = tuple(product(PROVIDERS, repeat=len(FLAGS)))
    scopes = tuple(tuple(i for i in FLAGS if mask & (1 << i)) for mask in range(1, 1 << len(FLAGS)))
    views = {(mapping, label): build_view(source(mapping), catalog)
             for mapping, (label, catalog) in product(mappings, EDITS.items())}
    all_keys = {(mapping, label, scope): keys(view, scope)
                for (mapping, label), view in views.items() for scope in scopes}
    counts = {mode: dict.fromkeys(("safe_reuse", "stale_reuse", "conservative_miss", "required_recompute"), 0)
              for mode in MODES}
    witnesses = {mode: {} for mode in MODES}
    queries = 0
    for before, after, scope, label in product(mappings, mappings, scopes, EDITS):
        first = reference(before, BASE, scope)
        second = reference(after, EDITS[label], scope)
        assert first == candidate_observations(views[before, "unchanged"], BASE, scope)
        assert second == candidate_observations(views[after, label], EDITS[label], scope)
        equal = first == second
        for mode in MODES:
            reused = all_keys[before, "unchanged", scope][mode] == all_keys[after, label, scope][mode]
            if reused:
                result = "safe_reuse" if equal else "stale_reuse"
            else:
                result = "conservative_miss" if equal else "required_recompute"
            counts[mode][result] += 1
            if result in {"stale_reuse", "conservative_miss"} and result not in witnesses[mode]:
                witnesses[mode][result] = example(before, after, scope, label)
        queries += 1
    assert counts["scoped-relation"]["stale_reuse"] == counts["exact-selector"]["stale_reuse"] == 0
    assert counts["target-set"]["stale_reuse"] and counts["one-trace"]["stale_reuse"]
    assert counts["scoped-relation"]["safe_reuse"] > counts["exact-selector"]["safe_reuse"]
    full = source(("left", "left", "right", "right"))
    unknown = {
        "missing-row": full.replace("when 3 call right\n", ""),
        "unknown-guard": full.replace("when 0", "when external"),
        "ambiguous-row": full + "when 0 call right\n",
    }
    assert all(build_view(text, BASE) is None for text in unknown.values())
    reordered = "".join(reversed(full.splitlines(keepends=True)))
    base_view = build_view(full, BASE)
    reordered_view = build_view(reordered, BASE)
    base_identity = keys(base_view, FLAGS)
    reordered_identity = keys(reordered_view, FLAGS)
    assert base_identity["exact-selector"] != reordered_identity["exact-selector"]
    assert base_identity["scoped-relation"] == reordered_identity["scoped-relation"]
    return {
        "format": PROFILE, "python": sys.version.split()[0], "git": version,
        "compared_pairs": queries,
        "counts": counts, "witnesses": witnesses, "unknown_selector_controls": unknown,
        "reordered_source_control": {"before": full, "after": reordered,
                                     "scoped_identity_preserved": True, "selector_identity_changed": True},
        "native_git_witness": git_witness(witnesses["target-set"]["stale_reuse"]),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(run(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
