"""Check exact selective retrieval from overlapping, pinned Provider offers."""

from collections import Counter
from contextlib import ExitStack
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from itertools import permutations
import json
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
INDEX = HERE.parents[1] / "PROTOTYPES" / "PACKAGE-INDEX-01"
sys.path.insert(0, str(INDEX))
from content_store import SQLiteContentStore, content_hash
from package_index import IndexError as LogicalError, logical_hash, merge


PAYLOAD = {
    "alpha": b"alpha payload\n",
    "beta": b"beta payload\n",
    "spare": b"unused payload in the selected snapshot\n",
    "outside": b"payload excluded from the approved catalogue\n",
}
HASH = {name: content_hash(binary) for name, binary in PAYLOAD.items()}
NAME = {key: name for name, key in HASH.items()}
APPROVED = frozenset({"a", "b"})


@dataclass(frozen=True)
class Offer:
    provider: str
    snapshot: str
    object_hash: str
    priority: int
    available: bool = True


class View:
    def __init__(self, backend, defect=None):
        self.backend = backend
        self.defect = defect
        self.streams = []

    @property
    def id(self):
        return self.backend.snapshot_id

    def metadata(self, key):
        value = self.backend.get_object(key)
        return {**value, "size": value["size"] + 1} if self.defect == "size" else value

    def open(self, key):
        self.streams.append(key)
        if self.defect == "payload":
            return BytesIO(b"bad fixture bytes")
        return self.backend.open_object(key)


def priority(offers, requested):
    return sorted((offer for offer in offers if offer.object_hash == requested and offer.available),
                  key=lambda offer: (offer.priority, offer.provider))


def direct_advertisement(offers, requested):
    selection = priority(offers, requested)
    return selection[0].provider if selection else None


def retrieve(index, views, offers, requested):
    if requested not in index:
        return None, ("outside-catalogue",)
    attempts = []
    for offer in priority(offers, requested):
        if offer.provider not in APPROVED:
            attempts.append("unauthorized-provider")
            continue
        view = views.get(offer.provider)
        if view is None or view.id != offer.snapshot:
            attempts.append("unavailable-exact-snapshot")
            continue
        try:
            metadata = view.metadata(requested)
            if metadata != index[requested]:
                attempts.append("metadata-mismatch")
                continue
            digest = sha256()
            size = 0
            with view.open(requested) as stream:
                for chunk in iter(lambda: stream.read(65536), b""):
                    digest.update(chunk)
                    size += len(chunk)
        except KeyError:
            attempts.append("missing-exact-object")
            continue
        if "sha256:" + digest.hexdigest() != requested or size != metadata["size"]:
            attempts.append("payload-mismatch")
            continue
        attempts.append("verified")
        return offer.provider, tuple(attempts)
    return None, tuple(attempts)


def indexed(names):
    return {
        "objects": [{"hash": HASH[name], "size": len(PAYLOAD[name]), "kind": "function"} for name in names],
        "dependencies": [], "exports": [], "modules": [],
    }


def store(path, names):
    result = SQLiteContentStore(path)
    for name in names:
        assert result.put_object(PAYLOAD[name], "function", ()) == HASH[name]
    return result


def compare(work):
    catalogues = (indexed(("alpha", "spare")), indexed(("alpha", "beta")))
    combined, reversed_combined = merge(*catalogues), merge(*reversed(catalogues))
    assert combined == reversed_combined
    index = {object_entry["hash"]: object_entry for object_entry in combined["objects"]}
    conflicting = indexed(("alpha",))
    conflicting["objects"][0]["size"] += 1
    try:
        merge(*catalogues, conflicting)
    except LogicalError:
        logical_conflict_rejected = True
    else:
        raise AssertionError("Incompatible logical records were silently combined")

    a = store(work / "a.sqlite", ("alpha", "spare", "outside"))
    b = store(work / "b.sqlite", ("alpha", "beta"))
    c = store(work / "c.sqlite", ("alpha",))
    with ExitStack() as resources:
        previous = resources.enter_context(a.open_snapshot())
        a.put_object(b"unrelated new snapshot generation", "function", ())
        current = resources.enter_context(a.open_snapshot())
        alternate = resources.enter_context(b.open_snapshot())
        outsider = resources.enter_context(c.open_snapshot())
        assert previous.snapshot_id != current.snapshot_id
        assert previous.get_object(HASH["alpha"]) == current.get_object(HASH["alpha"])

        def advertise(publisher, snapshot, name, rank, available=True):
            return Offer(publisher, snapshot.snapshot_id, HASH[name], rank, available)

        old_alpha = advertise("a", previous, "alpha", 1)
        new_alpha = advertise("a", current, "alpha", 1)
        new_beta = advertise("a", current, "beta", 1)
        alternate_alpha = advertise("b", alternate, "alpha", 2)
        alternate_beta = advertise("b", alternate, "beta", 2)
        outsider_alpha = advertise("c", outsider, "alpha", 0)
        cases = (
            ("known-single-source", "beta", (alternate_beta,), current, None, "b", ("verified",)),
            ("advertised-missing", "beta", (new_beta, alternate_beta), current, None, "b",
             ("missing-exact-object", "verified")),
            ("reported-unavailable", "beta",
             (advertise("a", current, "beta", 1, available=False), alternate_beta), current, None,
             "b", ("verified",)),
            ("stale-offer-with-fallback", "alpha", (old_alpha, alternate_alpha), current, None,
             "b", ("unavailable-exact-snapshot", "verified")),
            ("stale-offer-alone", "alpha", (old_alpha,), current, None, None,
             ("unavailable-exact-snapshot",)),
            ("old-view-still-retained", "alpha", (old_alpha,), previous, None, "a", ("verified",)),
            ("unapproved-source", "alpha", (outsider_alpha, alternate_alpha), current, None,
             "b", ("unauthorized-provider", "verified")),
            ("payload-claim-mismatch", "alpha", (new_alpha, alternate_alpha), current, "payload",
             "b", ("payload-mismatch", "verified")),
            ("reported-size-mismatch", "alpha", (new_alpha, alternate_alpha), current, "size",
             "b", ("metadata-mismatch", "verified")),
            ("missing-alternate", "beta", (new_beta,), current, None, None, ("missing-exact-object",)),
            ("wrong-object-offer", "beta", (new_alpha, alternate_beta), current, None, "b", ("verified",)),
            ("outside-approved-catalogue", "outside", (advertise("a", current, "outside", 1),),
             current, None, None, ("outside-catalogue",)),
            ("three-overlapping-offers", "alpha", (outsider_alpha, old_alpha, alternate_alpha),
             current, None, "b", ("unauthorized-provider", "unavailable-exact-snapshot", "verified")),
        )
        records = {}
        counts = Counter()
        for label, name, offers, selected_a, defect, provider, expected_attempts in cases:
            requested = HASH[name]
            for order in permutations(offers):
                views = {"a": View(selected_a, defect), "b": View(alternate), "c": View(outsider)}
                actual = retrieve(index, views, order, requested)
                if actual != (provider, expected_attempts):
                    raise AssertionError((label, actual, provider, expected_attempts))
                weak = direct_advertisement(order, requested)
                streams = {source: [NAME[key] for key in view.streams] for source, view in views.items()
                           if view.streams}
                if any(key != requested for view in views.values() for key in view.streams):
                    raise AssertionError("Selective retrieval opened an unrelated payload")
                counts["exact_matches"] += 1
                counts["wrong_availability_only_selection"] += weak != provider
                records[label] = {
                    "provider": provider, "attempts": expected_attempts,
                    "availability_only_provider": weak, "payloads_opened": streams,
                }

    watched = (HERE / "run.py", INDEX / "content_store.py", INDEX / "package_index.py")
    return {
        "sqlite": sqlite3.sqlite_version,
        "combined_logical_index": logical_hash(combined),
        "logical_conflict_rejected": logical_conflict_rejected,
        "scenarios": len(records),
        "counts": counts,
        "observations": records,
        "source_sha256": {path.relative_to(HERE.parents[3]).as_posix(): sha256(path.read_bytes()).hexdigest()
                          for path in watched},
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-multi-provider-") as temp:
        print(json.dumps(compare(Path(temp)), indent=2))
