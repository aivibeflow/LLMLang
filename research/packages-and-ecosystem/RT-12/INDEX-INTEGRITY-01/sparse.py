"""Verify that optional sparse directories cannot certify exact-index absence alone."""

from bisect import bisect_right
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
from pathlib import Path
import struct
import sys
import zlib

HERE = Path(__file__).resolve().parent
COMPRESSION = HERE.parent / "INDEX-COMPRESSION-01"
sys.path.insert(0, str(COMPRESSION))
from run import CODECS, KEY_SIZE, ROW_SIZE, in_memory, make_fixture

DIRECTORY_ENTRY = struct.Struct(">32sQI32s")


def digest(raw):
    return sha256(raw).digest()


@dataclass(frozen=True)
class Pin:
    codec: str
    block_rows: int
    logical_sha256: bytes
    directory_sha256: bytes


@dataclass(frozen=True)
class OptionalDirectory:
    logical_sha256: bytes
    payload: bytes
    self_sha256: bytes


@dataclass(frozen=True)
class Index:
    directory: OptionalDirectory | None
    compressed_blocks: bytes
    canonical: bytes | None


def create_projection(canonical, codec, block_rows):
    width = block_rows * ROW_SIZE
    data = bytearray()
    directory = bytearray()
    for start in range(0, len(canonical), width):
        rows = canonical[start:start + width]
        compressed = CODECS[codec].compress(rows)
        directory.extend(DIRECTORY_ENTRY.pack(rows[:KEY_SIZE], len(data),
                                               len(compressed), digest(compressed)))
        data.extend(compressed)
    encoded = bytes(directory)
    root = digest(canonical)
    entry = OptionalDirectory(root, encoded, digest(encoded))
    return Pin(codec, block_rows, root, entry.self_sha256), Index(entry, bytes(data), canonical)


def try_view(index, pin, anchored, key):
    sidecar = index.directory
    if sidecar is None or sidecar.logical_sha256 != pin.logical_sha256:
        return "unavailable", None
    expected = pin.directory_sha256 if anchored else sidecar.self_sha256
    if digest(sidecar.payload) != expected or len(sidecar.payload) % DIRECTORY_ENTRY.size:
        return "unavailable", None
    entries = tuple(DIRECTORY_ENTRY.iter_unpack(sidecar.payload))
    starts = tuple(boundary for boundary, _, _, _ in entries)
    if len(set(starts)) != len(starts) or tuple(sorted(starts)) != starts:
        return "unavailable", None
    selected = bisect_right(starts, key) - 1
    if selected < 0:
        return "missing", None
    _, offset, length, expected_block = entries[selected]
    block = index.compressed_blocks[offset:offset + length]
    if len(block) != length or digest(block) != expected_block:
        return "unavailable", None
    try:
        canonical = CODECS[pin.codec].decompress(block)
    except (EOFError, OSError, zlib.error):
        return "unavailable", None
    if len(canonical) % ROW_SIZE or canonical[:KEY_SIZE] != starts[selected]:
        return "unavailable", None
    value = in_memory(canonical, key)
    return ("found", digest(value).hex()) if value is not None else ("missing", None)


def resolve(index, pin, key, anchored, recover):
    result = try_view(index, pin, anchored, key)
    if result[0] != "unavailable":
        return (*result, "sparse")
    if not recover or index.canonical is None or digest(index.canonical) != pin.logical_sha256:
        return ("unavailable", None, "refused")
    rebuilt_pin, rebuilt = create_projection(index.canonical, pin.codec, pin.block_rows)
    if rebuilt_pin != pin:
        raise ValueError("Canonical rebuild does not match the declared projection")
    return (*try_view(rebuilt, pin, anchored=True, key=key), "rebuilt")


def sidecar_for(encoded, pin):
    return OptionalDirectory(pin.logical_sha256, encoded, digest(encoded))


def alter_selected_row(index, pin, key):
    entries = list(DIRECTORY_ENTRY.iter_unpack(index.directory.payload))
    starts = [entry[0] for entry in entries]
    selected = bisect_right(starts, key) - 1
    boundary, offset, length, _ = entries[selected]
    decompressed = CODECS[pin.codec].decompress(index.compressed_blocks[offset:offset + length])
    position = next(pos for pos in range(0, len(decompressed), ROW_SIZE)
                    if decompressed[pos:pos + KEY_SIZE] == key)
    changed = bytearray(decompressed)
    changed[position + ROW_SIZE - 1] ^= 1
    altered = CODECS[pin.codec].compress(changed)
    entries[selected] = (boundary, len(index.compressed_blocks), len(altered), digest(altered))
    encoded = b"".join(DIRECTORY_ENTRY.pack(*entry) for entry in entries)
    return replace(index, directory=sidecar_for(encoded, pin),
                   compressed_blocks=index.compressed_blocks + altered)


def cases(index, pin, key, other_projection):
    encoded = index.directory.payload
    rows = list(DIRECTORY_ENTRY.iter_unpack(encoded))
    dropped_first = encoded[DIRECTORY_ENTRY.size:]
    # The first block contains the correct first key but ends just before the chosen hit.
    offset, length = rows[0][1:3]
    original = CODECS[pin.codec].decompress(index.compressed_blocks[offset:offset + length])
    shortened = CODECS[pin.codec].compress(original[:16 * ROW_SIZE])
    wrong_offset = DIRECTORY_ENTRY.pack(rows[0][0], len(index.compressed_blocks),
                                       len(shortened), digest(shortened)) + dropped_first
    corrupted_first = bytes([index.compressed_blocks[0] ^ 1]) + index.compressed_blocks[1:]
    return {
        "unchanged": (index, "sparse"),
        "no-optional-directory": (replace(index, directory=None), "rebuilt"),
        "stale-directory-same-logical-root": (replace(index, directory=other_projection.directory), "rebuilt"),
        "truncated-directory-disagrees-with-checksum":
            (replace(index, directory=replace(index.directory, payload=encoded[:-1])), "rebuilt"),
        "omitted-leading-block-and-self-checksum":
            (replace(index, directory=sidecar_for(dropped_first, pin)), "rebuilt"),
        "wrong-pointer-and-self-checksum":
            (replace(index, directory=sidecar_for(wrong_offset, pin),
                     compressed_blocks=index.compressed_blocks + shortened), "rebuilt"),
        "changed-row-and-self-checksum": (alter_selected_row(index, pin, key), "rebuilt"),
        "truncated-block-under-valid-directory":
            (replace(index, compressed_blocks=index.compressed_blocks[1:]), "rebuilt"),
        "corrupt-only-first-block-under-valid-directory":
            (replace(index, compressed_blocks=corrupted_first), "route-by-query"),
        "missing-directory-and-missing-canonical":
            (replace(index, directory=None, canonical=None), "refused"),
        "missing-directory-and-wrong-canonical":
            (replace(index, directory=None, canonical=index.canonical[ROW_SIZE:]), "refused"),
    }


def run():
    canonical, _, oracle = make_fixture()
    gzip, baseline = create_projection(canonical, "gzip", 64)
    larger, larger_blocks = create_projection(canonical, "gzip", 256)
    bzip, bzip_blocks = create_projection(canonical, "bzip2", 64)
    pins = (gzip, larger, bzip)
    assert len({pin.logical_sha256 for pin in pins}) == 1
    assert len({pin.directory_sha256 for pin in pins}) == len(pins)
    early, middle = sorted(oracle)[17], sorted(oracle)[4097]
    missing = sha256(b"fixture-absent-lookup").digest()
    assert missing not in oracle
    requests = {"leading-hit": early, "middle-hit": middle, "miss": missing}
    results = {}
    false_self_checked = 0
    for name, (index, recovery) in cases(baseline, gzip, early, larger_blocks).items():
        results[name] = {}
        for lookup, key in requests.items():
            actual = resolve(index, gzip, key, anchored=True, recover=True)
            weak = resolve(index, gzip, key, anchored=False, recover=False)
            correct = ("found", digest(oracle[key]).hex()) if key in oracle else ("missing", None)
            if recovery == "refused":
                assert actual == ("unavailable", None, "refused")
            else:
                assert actual[:2] == correct, (name, lookup, actual, correct)
                expected_route = recovery
                if recovery == "route-by-query":
                    expected_route = "rebuilt" if lookup == "leading-hit" else "sparse"
                assert actual[2] == expected_route, (name, lookup, actual, expected_route)
            false_self_checked += weak[0] in {"found", "missing"} and weak[:2] != correct
            results[name][lookup] = {"oracle": correct, "self_checked": weak, "pinned": actual}

    assert false_self_checked == 3
    assert results["omitted-leading-block-and-self-checksum"]["leading-hit"]["self_checked"][0] == "missing"
    assert results["changed-row-and-self-checksum"]["leading-hit"]["self_checked"][:2] != (
        "found", digest(oracle[early]).hex())
    for pin, index in ((larger, larger_blocks), (bzip, bzip_blocks)):
        for key in requests.values():
            expected = ("found", digest(oracle[key]).hex()) if key in oracle else ("missing", None)
            assert resolve(index, pin, key, anchored=True, recover=True) == (*expected, "sparse")
    return {
        "source_sha256": {str(path.relative_to(HERE.parent)): digest(path.read_bytes()).hex()
                          for path in (HERE / "sparse.py", COMPRESSION / "run.py")},
        "projections": [{name: value.hex() if isinstance(value, bytes) else value
                         for name, value in asdict(pin).items()} for pin in pins],
        "queries": {name: key.hex() for name, key in requests.items()},
        "lookup_cases": len(requests) * len(results),
        "false_results_when_self_checked": false_self_checked,
        "results": results,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
