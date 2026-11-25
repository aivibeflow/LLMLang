"""Compare directory read traffic and immutable update bytes, excluding block payload I/O."""

from hashlib import sha256
import json
from pathlib import Path
from random import Random
import struct
from tempfile import TemporaryDirectory


ENTRY = struct.Struct(">32sQI32s")
BLOCK_COUNTS = (16, 128, 4096, 65536)
PAGE_ENTRIES = 64
MODES = ("omitted", "flat-retained", "flat-seek", "two-level")
SPACING = 4


def key(number):
    return number.to_bytes(32, "big")


def row(number, modified=False):
    body = f"block-index-{number}-{int(modified)}".encode()
    return ENTRY.pack(key((number + 1) * SPACING), number * 512, 512, sha256(body).digest())


def directory_bytes(count):
    return b"".join(row(index) for index in range(count))


def pages(flat):
    width = ENTRY.size * PAGE_ENTRIES
    parts = tuple(flat[offset:offset + width] for offset in range(0, len(flat), width))
    root = b"".join(ENTRY.pack(part[:32], index * width, len(part), sha256(part).digest())
                    for index, part in enumerate(parts))
    return root, parts


class Reader:
    def __init__(self):
        self.bytes = 0
        self.calls = 0

    def read(self, file, offset, size):
        file.seek(offset)
        result = file.read(size)
        if len(result) != size:
            raise ValueError("Incomplete directory read")
        self.bytes += size
        self.calls += 1
        return result


def candidate_row(read, count, wanted):
    lower, upper = 0, count
    candidate = None
    while lower < upper:
        middle = (lower + upper) // 2
        sample = read(middle)
        if sample[:32] <= wanted:
            candidate = sample
            lower = middle + 1
        else:
            upper = middle
    return candidate


def indexed_rows(data):
    def read(index):
        offset = index * ENTRY.size
        return data[offset:offset + ENTRY.size]
    return read


def flat_candidates(directory, counter, wanted, count, retained):
    with directory.open("rb", buffering=0) as file:
        if retained:
            read = indexed_rows(counter.read(file, 0, count * ENTRY.size))
        else:
            def read(index):
                return counter.read(file, index * ENTRY.size, ENTRY.size)
        return [candidate_row(read, count, value) for value in wanted]


def two_level_candidates(directory, counter, wanted, root_size):
    results = []
    retained = {}
    with (directory / "root").open("rb", buffering=0) as root, (
        directory / "leaves"
    ).open("rb", buffering=0) as leaves:
        root_rows = indexed_rows(counter.read(root, 0, root_size))
        for value in wanted:
            candidate = candidate_row(root_rows, root_size // ENTRY.size, value)
            if candidate is None:
                results.append(None)
                continue
            _, offset, length, commitment = ENTRY.unpack(candidate)
            if offset not in retained:
                page = counter.read(leaves, offset, length)
                if sha256(page).digest() != commitment:
                    raise ValueError("Unexpected page commitment")
                retained[offset] = page
            read = indexed_rows(retained[offset])
            results.append(candidate_row(read, length // ENTRY.size, value))
    return results


def query_profiles(count):
    seeded = Random(333)
    focus = count // 2
    cluster_start = (focus // PAGE_ENTRIES) * PAGE_ENTRIES
    cluster_end = min(count, cluster_start + PAGE_ENTRIES)
    lower = (cluster_start + 1) * SPACING
    upper = (cluster_end + 1) * SPACING - 1
    maximum = (count + 1) * SPACING + 1
    return {
        "single": [focus * SPACING + 3],
        "dispersed-64": [0, SPACING, maximum, *(seeded.randrange(SPACING, maximum) for _ in range(61))],
        "clustered-64": [seeded.randrange(lower, upper + 1) for _ in range(64)],
    }


def verify_case(directory, count):
    directory.mkdir()
    flat = directory_bytes(count)
    root, leaves = pages(flat)
    (directory / "canonical-headers").write_bytes(flat)
    (directory / "flat").write_bytes(flat)
    (directory / "root").write_bytes(root)
    (directory / "leaves").write_bytes(b"".join(leaves))
    results = {}
    for name, queries in query_profiles(count).items():
        wanted = [key(value) for value in queries]
        expected = [None if value < SPACING else row(min(count, value // SPACING) - 1)
                    for value in queries]
        report = {}
        for mode in MODES:
            reader = Reader()
            if mode == "two-level":
                found = two_level_candidates(directory, reader, wanted, len(root))
            else:
                path = directory / ("canonical-headers" if mode == "omitted" else "flat")
                found = flat_candidates(path, reader, wanted, count, retained=mode != "flat-seek")
            if found != expected:
                raise AssertionError((count, name, mode, "candidate block mismatch"))
            report[mode] = {"read_calls": reader.calls, "read_bytes": reader.bytes}
        results[name] = {"queries": len(queries), "modes": report}

    changed_index = count // 2
    start = changed_index * ENTRY.size
    changed = flat[:start] + row(changed_index, modified=True) + flat[start + ENTRY.size:]
    new_root, new_leaves = pages(changed)
    changed_pages = [index for index, (before, after) in enumerate(zip(leaves, new_leaves, strict=True))
                     if before != after]
    if changed_pages != [changed_index // PAGE_ENTRIES] or new_root == root:
        raise ValueError("Unexpected directory replacement")
    before_root = tuple(ENTRY.iter_unpack(root))
    after_root = tuple(ENTRY.iter_unpack(new_root))
    if sum(before != after for before, after in zip(before_root, after_root, strict=True)) != 1:
        raise ValueError("Unexpected root changes")

    return {
        "blocks": count,
        "level_two_pages": len(leaves),
        "derived_storage_bytes": {"omitted": 0, "flat": len(flat), "two-level": len(flat) + len(root)},
        "derived_bytes_written_for_one_replacement": {
            "omitted": 0,
            "flat": len(changed),
            "two-level": len(new_root) + len(new_leaves[changed_pages[0]]),
        },
        "queries": results,
    }


def verify():
    with TemporaryDirectory(prefix="llmlang-sparse-directory-") as scratch:
        work = Path(scratch)
        matrix = [verify_case(work / str(count), count) for count in BLOCK_COUNTS]
    return {
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "entry_bytes": ENTRY.size,
        "leaf_entries": PAGE_ENTRIES,
        "scales": matrix,
        "matched_routes": sum(profile["queries"] * len(MODES) for scale in matrix
                              for profile in scale["queries"].values()),
    }


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
