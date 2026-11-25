"""Compare local and shared CAS availability under exact repository closures."""

import hashlib
import json
from pathlib import Path
import platform
from tempfile import TemporaryDirectory


def json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def graph_fixture(common_count):
    shared = {}
    previous = None
    for index in range(common_count):
        payload = json_bytes({"common": index, "content": "public semantic component " * 12,
                              "children": [previous] if previous else []})
        previous = sha(payload)
        shared[previous] = payload
    roots = {}
    for repo in ("a", "b"):
        payload = json_bytes({"local": repo, "children": [previous]})
        root = sha(payload)
        roots[repo] = {
            "manifest": {"root": root, "closure": sorted([*shared, root])},
            "objects": shared | {root: payload},
        }
    return roots


def install(directory, objects):
    directory.mkdir()
    for address, data in objects.items():
        assert sha(data) == address
        (directory / address).write_bytes(data)


def verify(manifest, read):
    allowed = set(manifest["closure"])
    found = {}
    pending = [manifest["root"]]
    while pending:
        address = pending.pop()
        if address in found:
            continue
        if address not in allowed:
            return "unlisted-required-object", {}
        try:
            data = read(address)
        except FileNotFoundError:
            return "unavailable", {}
        if sha(data) != address:
            return "corrupt-object", {}
        found[address] = data
        pending.extend(json.loads(data)["children"])
    if allowed != found.keys():
        return "closure-mismatch", {}
    return "verified-closure", found


def bytes_on_disk(directory):
    return sum(path.stat().st_size for path in directory.iterdir() if path.is_file())


def study(directory, count):
    roots = graph_fixture(count)
    full = roots["a"]["objects"] | roots["b"]["objects"]
    shared = directory / "shared"
    local_a = directory / "local-a"
    local_b = directory / "local-b"
    hybrid_a = directory / "pinned-a"
    offline = directory / "absent-shared-store"
    install(shared, full)
    install(local_a, roots["a"]["objects"])
    install(local_b, roots["b"]["objects"])

    manifest_a = roots["a"]["manifest"]
    manifest_b = roots["b"]["manifest"]

    def check(manifest, location):
        status, restored = verify(manifest, lambda address: (location / address).read_bytes())
        return status, len(restored)

    admitted, contents = verify(manifest_a, lambda address: (shared / address).read_bytes())
    assert admitted == "verified-closure"
    assert contents == roots["a"]["objects"]
    install(hybrid_a, contents)
    cases = {
        "a_local_offline": check(manifest_a, local_a),
        "b_local_offline": check(manifest_b, local_b),
        "a_selected_shared_root": check(manifest_a, shared),
        "b_selected_shared_root": check(manifest_b, shared),
        "shared_store_unavailable": check(manifest_a, offline),
        "pinned_a_offline": check(manifest_a, hybrid_a),
        "unmaterialized_b_offline": check(manifest_b, hybrid_a),
        "peer_root_in_a_inventory": check(manifest_a | {"closure": [
            *manifest_a["closure"], manifest_b["root"]
        ]}, shared),
        "peer_root_missing_from_authorized_inventory": check(manifest_a | {"root": manifest_b["root"]}, shared),
    }
    measured = {
        "separate_local_object_bytes": bytes_on_disk(local_a) + bytes_on_disk(local_b),
        "shared_object_bytes": bytes_on_disk(shared),
        "shared_with_one_local_pin_object_bytes": bytes_on_disk(shared) + bytes_on_disk(hybrid_a),
    }
    assert measured["shared_object_bytes"] < measured["separate_local_object_bytes"]
    assert len(full) == count + 2
    assert all(cases[name] == ("verified-closure", count + 1) for name in (
        "a_local_offline", "b_local_offline", "a_selected_shared_root", "b_selected_shared_root", "pinned_a_offline"
    ))
    assert cases["shared_store_unavailable"] == cases["unmaterialized_b_offline"] == ("unavailable", 0)
    assert cases["peer_root_in_a_inventory"] == ("closure-mismatch", 0)
    assert cases["peer_root_missing_from_authorized_inventory"] == ("unlisted-required-object", 0)

    core = next(address for address in manifest_a["closure"] if address != manifest_a["root"])
    (shared / core).write_bytes(b"corrupted fixture object")
    cases["corrupted_shared_payload"] = check(manifest_a, shared)
    cases["local_pin_after_shared_corruption"] = check(manifest_a, hybrid_a)
    assert cases["corrupted_shared_payload"] == ("corrupt-object", 0)
    assert cases["local_pin_after_shared_corruption"] == ("verified-closure", count + 1)
    return {"objects_per_repository": count + 1, "shared_unique_objects": len(full),
            "root_ids": {"a": manifest_a["root"], "b": manifest_b["root"]},
            "object_byte_counts": measured, "controls": cases}


def main():
    data = {}
    with TemporaryDirectory(prefix="llmlang-repository-closures-") as scratch:
        for count in (4, 64, 256):
            directory = Path(scratch) / str(count)
            directory.mkdir()
            data[count] = study(directory, count)
    return {
        "schema": "llmlang-rt12-repository-closure-scopes/1", "python": platform.python_version(),
        "runner_sha256": sha(Path(__file__).read_bytes()),
        "measurement": "regular file object bytes, excluding small selection manifests",
        "cases": data,
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
