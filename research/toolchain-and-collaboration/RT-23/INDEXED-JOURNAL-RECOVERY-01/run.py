"""Compare native Git receipt lookup from one pinned publication journal."""

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
PROTOTYPE = HERE.parents[2] / "PROTOTYPES" / "DEPENDENCY-GRAPH-01"
sys.path.insert(0, str(PROTOTYPE))

from src.semantic_graph import canonical_bytes
from tests import test_rt23_commit_recovery as recovery
from tests import test_rt24_merge_tree_gate as source

REFS = {policy: f"refs/llmlang/journal/{policy}" for policy in ("scan", "indexed")}
HISTORY = 64
WINDOW = 8
FORMAT = "llmlang-rt23-journal-receipt/1"


@dataclass(frozen=True)
class Request:
    scope: str
    plan: recovery.Prepared

    @property
    def identity(self):
        return [self.scope, self.plan.operation]

    @property
    def path(self):
        digest = sha256(canonical_bytes(self.identity)).hexdigest()
        return f"receipts/{digest[:2]}/{digest[2:]}.json"


def git(repo, *args, data=None):
    return source.git(repo, *args, stdin=data).decode().strip()


def blob(repo, value):
    return git(repo, "hash-object", "-w", "--stdin", data=canonical_bytes(value))


def tree(repo, entries):
    raw = "".join(f"{mode} {kind} {oid}\t{name}\n" for name, (mode, kind, oid) in entries.items())
    return git(repo, "mktree", data=raw.encode())


def entries(repo, revision, path=None):
    spec = f"{revision}:{path}" if path is not None else revision
    data = git(repo, "ls-tree", spec)
    result = {}
    for line in data.splitlines():
        metadata, name = line.split("\t")
        mode, kind, oid = metadata.split()
        result[name] = (mode, kind, oid)
    return result


def read_request(repo, revision, path):
    listed = git(repo, "ls-tree", "--full-tree", revision, "--", path)
    if not listed:
        return None
    metadata, name = listed.split("\t")
    mode, kind, oid = metadata.split()
    assert (mode, kind, name) == ("100644", "blob", path)
    raw = source.git(repo, "cat-file", "blob", oid)
    record = json.loads(raw)
    assert canonical_bytes(record) == raw
    assert record["format"] == FORMAT
    assert record["branch"] == recovery.BRANCH
    plan = record["plan"]
    return Request(record["scope"], recovery.Prepared(**{**plan, "parents": tuple(plan["parents"])}))


def initialize(repo, backend):
    git(repo, "init", "--quiet", "--template=", "--initial-branch=main", "--object-format=sha1",
        f"--ref-format={backend}")
    item = source.row("contract", source.declaration("contract", "contract:journal", {"revision": 0}))
    base = source.commit(repo, {source.MANIFEST: source.manifest(source.CONTRACT), source.CONTRACT: [item]})
    empty = tree(repo, {})
    indexed = tree(repo, {"receipts": ("040000", "tree", empty)})
    genesis = {
        "scan": recovery.commit_object(repo, empty, (base,), "journal genesis"),
        "indexed": recovery.commit_object(repo, indexed, (base,), "indexed journal genesis"),
    }
    for policy, ref in REFS.items():
        git(repo, "update-ref", ref, genesis[policy])
    return base, genesis


def prepare(repo, predecessor, revision):
    item = source.row("contract", source.declaration("contract", "contract:journal", {"revision": revision}))
    original = entries(repo, predecessor, "program")
    original["contract.json"] = ("100644", "blob", blob(repo, [item]))
    candidate_tree = tree(repo, {"program": ("040000", "tree", tree(repo, original))})
    candidate = recovery.commit_object(repo, candidate_tree, (predecessor,), f"request revision {revision}")
    _, snapshot = source.import_closed(source.read_inventory(repo, candidate))
    namespace = ("project:A", "project:B")[(revision - 1) % 2]
    operation = f"request-{(revision - 1) // 2:03d}"
    plan = recovery.Prepared(operation, candidate_tree, snapshot.root_hash, (predecessor,), candidate)
    return Request(namespace, plan)


def build_entries(repo, previous, request):
    record = {"format": FORMAT, "branch": recovery.BRANCH, "scope": request.scope, "plan": asdict(request.plan)}
    receipt = ("100644", "blob", blob(repo, record))
    linear = tree(repo, {"publication.json": receipt})
    root = entries(repo, previous["indexed"], "receipts")
    _, shard, filename = request.path.split("/")
    bucket = entries(repo, previous["indexed"], f"receipts/{shard}") if shard in root else {}
    if filename in bucket:
        raise ValueError("request already has a receipt")
    bucket[filename] = receipt
    root[shard] = ("040000", "tree", tree(repo, bucket))
    indexed = tree(repo, {"publication.json": receipt, "receipts": ("040000", "tree", tree(repo, root))})
    return {
        policy: recovery.commit_object(repo, candidate_tree, (previous[policy], request.plan.candidate),
                                       "journal publication")
        for policy, candidate_tree in (("scan", linear), ("indexed", indexed))
    }


def compare_and_swap(repo, previous, proposed):
    for policy, ref in REFS.items():
        git(repo, "update-ref", ref, proposed[policy], previous[policy])


def verify_index(repo, heads):
    """Audit every indexed path and blob against the original first-parent receipts."""
    commits = git(repo, "rev-list", "--first-parent", heads["scan"]).splitlines()
    expected = {}
    for entry in commits[:-2]:
        stored = read_request(repo, entry, "publication.json")
        assert stored is not None and stored.path not in expected
        expected[stored.path] = entries(repo, entry)["publication.json"]
    listed = git(repo, "ls-tree", "-r", "--full-tree", heads["indexed"], "--", "receipts")
    observed = {}
    for line in listed.splitlines():
        metadata, path = line.split("\t")
        observed[path] = tuple(metadata.split())
    assert observed == expected
    return len(observed)


def verify_match(repo, expected, stored):
    if stored != expected:
        return "request-conflict"
    assert recovery.matches_candidate(repo, stored.plan)
    return "published"


def scan(repo, head, request, limit=None):
    checked = 0
    current = head
    while limit is None or checked < limit:
        parents = git(repo, "show", "-s", "--format=%P", current).split()
        if len(parents) == 1:
            assert not entries(repo, current)
            return "undecided", checked
        current_parent, candidate = parents
        stored = read_request(repo, current, "publication.json")
        assert stored is not None and stored.plan.candidate == candidate
        checked += 1
        if stored.identity == request.identity:
            return verify_match(repo, request, stored), checked
        current = current_parent
    return "history-window-exhausted", checked


def indexed(repo, head, request):
    stored = read_request(repo, head, request.path)
    if stored is None:
        return "undecided", 0
    return verify_match(repo, request, stored), 1


def counts(repo, head):
    oids = git(repo, "rev-list", "--objects", "--no-object-names", head)
    sizes = git(repo, "cat-file", "--batch-check=%(objecttype) %(objectsize)", data=(oids + "\n").encode())
    summary = {}
    for row in sizes.splitlines():
        kind, size = row.split()
        values = summary.setdefault(kind, {"objects": 0, "uncompressed_bytes": 0})
        values["objects"] += 1
        values["uncompressed_bytes"] += int(size)
    return summary


def query(repo, name, heads, request, expected):
    observed = {
        "scan": scan(repo, heads["scan"], request),
        "window": scan(repo, heads["scan"], request, WINDOW),
        "indexed": indexed(repo, heads["indexed"], request),
    }
    assert observed["scan"][0] == observed["indexed"][0] == expected, (name, observed)
    if observed["scan"][1] > WINDOW:
        assert observed["window"] == ("history-window-exhausted", WINDOW)
    return {"case": name, "identity": request.identity, "candidate": request.plan.candidate,
            "expected": expected, "heads": heads,
            "observations": {route: {"result": result, "receipts_examined": count}
                             for route, (result, count) in observed.items()}}


def experiment(directory, backend):
    repo = directory / "producer"
    repo.mkdir(parents=True)
    base, heads = initialize(repo, backend)
    histories = [heads]
    requests = []
    predecessor = base
    for revision in range(1, HISTORY + 1):
        request = prepare(repo, predecessor, revision)
        updated = build_entries(repo, heads, request)
        compare_and_swap(repo, heads, updated)
        heads = updated
        histories.append(heads)
        requests.append(request)
        predecessor = request.plan.candidate

    pending = prepare(repo, predecessor, HISTORY + 1)
    proposed = build_entries(repo, heads, pending)
    before = query(repo, "prepared_objects_before_cas", heads, pending, "undecided")
    assert all(recovery.ref(repo, ref) == heads[policy] for policy, ref in REFS.items())
    compare_and_swap(repo, heads, proposed)
    after = query(repo, "same_request_after_cas", proposed, pending, "published")
    for policy, ref in REFS.items():
        try:
            git(repo, "update-ref", ref, proposed[policy], heads[policy])
        except subprocess.CalledProcessError as error:
            assert b"expected" in error.stderr
        else:
            raise AssertionError("stale journal comparison unexpectedly succeeded")
    assert recovery.ref(repo, recovery.BRANCH) == base

    try:
        build_entries(repo, proposed, requests[0])
    except ValueError as error:
        assert str(error) == "request already has a receipt"
    else:
        raise AssertionError("duplicate appended")

    clone = directory / "clone"
    git(directory, "clone", "--quiet", "--no-local", str(repo), str(clone))
    assert all(recovery.ref(clone, ref) is None for ref in REFS.values())
    git(clone, "fetch", "--quiet", "origin", *(f"{ref}:{ref}" for ref in REFS.values()))
    git(clone, "fsck", "--full")
    assert all(recovery.ref(clone, ref) == proposed[policy] for policy, ref in REFS.items())
    assert recovery.ref(clone, recovery.BRANCH) == base

    old = requests[0]
    different_commit = recovery.commit_object(repo, old.plan.tree, old.plan.parents, "same tree, different candidate")
    conflicting = replace(old, plan=replace(old.plan, candidate=different_commit))
    absent = replace(old, plan=replace(old.plan, operation="unseen request"))
    cases = [
        ("oldest", proposed, old, "published"),
        ("same_key_other_scope", proposed, requests[1], "published"),
        ("middle", proposed, requests[HISTORY // 2 - 1], "published"),
        ("recent", proposed, requests[-1], "published"),
        ("latest", proposed, pending, "published"),
        ("same_key_different_commit", proposed, conflicting, "request-conflict"),
        ("absent_key", proposed, absent, "undecided"),
        ("future_key_at_pinned_head", histories[HISTORY // 2], pending, "undecided"),
        ("old_key_at_pinned_head", histories[HISTORY // 2], old, "published"),
    ]
    assert requests[0].plan.operation == requests[1].plan.operation
    assert requests[0].path != requests[1].path
    assert len({request.path.split("/")[1] for request in requests}) < HISTORY
    local = [query(repo, *case) for case in cases]
    restored = [query(clone, *case) for case in cases]
    assert local == restored
    audited = {"prefix": verify_index(clone, histories[HISTORY // 2]),
               "latest": verify_index(clone, proposed)}
    assert audited == {"prefix": HISTORY // 2, "latest": HISTORY + 1}
    return {"ref_backend": backend, "ordinary_branch": base, "clean_clone_replays": len(restored),
            "reuse_rejected": True, "stale_cas_rejected": True, "audited_index": audited,
            "cas_boundary": [before, after], "queries": restored,
            "reachable_objects": {policy: counts(clone, head) for policy, head in proposed.items()}}


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-indexed-journal-") as scratch:
        directory = Path(scratch)
        version = git(directory, "--version")
        assert version == "git version 2.52.0" and sys.platform == "linux"
        cases = [experiment(directory / backend, backend) for backend in ("files", "reftable")]
    assert {**cases[0], "ref_backend": "reftable"} == cases[1]
    artifacts = [Path(__file__), PROTOTYPE / "tests" / "test_rt23_commit_recovery.py",
                 PROTOTYPE / "tests" / "test_rt24_merge_tree_gate.py"]
    result = {"schema": "llmlang-rt23-indexed-journal-recovery/1", "git": version,
              "python": sys.version.split()[0], "history": HISTORY, "window": WINDOW,
              "source_digests": {path.name: sha256(path.read_bytes()).hexdigest() for path in artifacts},
              "profiles": ["files", "reftable"], "results": cases[0] | {"ref_backend": "both"}}
    print(json.dumps(result, indent=2, ensure_ascii=False))
