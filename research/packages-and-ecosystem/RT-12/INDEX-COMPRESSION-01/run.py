"""Compare exact lookup and ordered scan across package-index compression layouts."""

import argparse
from bisect import bisect_right
import bz2
import csv
from dataclasses import dataclass
import gzip
from hashlib import sha256
import json
from pathlib import Path
import platform
from random import Random
import struct
from tempfile import TemporaryDirectory
from time import perf_counter_ns
import tracemalloc
import zlib


KEY_SIZE = 32
ROW_SIZE = 64
ROWS = 8192
QUERY_COUNT = 64
SCAN_ROWS = 256
BLOCK_ROWS = (64, 256, 1024)
HEADER = struct.Struct(">I")
DIRECTORY_ROW = struct.Struct(">32sQI")


@dataclass(frozen=True)
class Codec:
    compress: object
    decompress: object
    open_stream: object


CODECS = {
    "gzip": Codec(lambda data: gzip.compress(data, compresslevel=3, mtime=0),
                  gzip.decompress, lambda file: gzip.GzipFile(fileobj=file, mode="rb")),
    "bzip2": Codec(lambda data: bz2.compress(data, compresslevel=3),
                   bz2.decompress, lambda file: bz2.BZ2File(file, "rb")),
}


@dataclass(frozen=True)
class Layout:
    name: str
    codec: str
    block_rows: int = 0


class CountingReader:
    def __init__(self, file):
        self.file = file
        self.bytes = 0

    def read(self, size=-1):
        value = self.file.read(size)
        self.bytes += len(value)
        return value

    def seek(self, position, whence=0):
        return self.file.seek(position, whence)

    def tell(self):
        return self.file.tell()

    def seekable(self):
        return self.file.seekable()


def make_fixture():
    by_key = {}
    for number in range(ROWS):
        key = sha256(f"object/{number:08x}".encode()).digest()
        prefix = f"package/{number % 32:02d}".encode().ljust(16, b"\0")
        metadata = struct.pack(">IIII", number % 7, 1, 0, number % 3)
        by_key[key] = key + prefix + metadata
    ordered = b"".join(row for _, row in sorted(by_key.items()))
    rng = Random(522)
    query = rng.sample(sorted(by_key), QUERY_COUNT // 2)
    query.extend(sha256(f"missing/{number:08x}".encode()).digest()
                 for number in range(QUERY_COUNT // 2))
    rng.shuffle(query)
    if sum(key in by_key for key in query) != QUERY_COUNT // 2:
        raise ValueError("Queries must cover an equal number of hits and misses")
    return ordered, query, by_key


def encode(layout, ordered):
    if not layout.codec:
        return ordered, 0
    codec = CODECS[layout.codec]
    if not layout.block_rows:
        return codec.compress(ordered), 0
    width = layout.block_rows * ROW_SIZE
    slices = [ordered[start:start + width] for start in range(0, len(ordered), width)]
    offset = HEADER.size + len(slices) * DIRECTORY_ROW.size
    directory = bytearray(HEADER.pack(len(slices)))
    blocks = []
    for block in slices:
        compressed = codec.compress(block)
        directory.extend(DIRECTORY_ROW.pack(block[:KEY_SIZE], offset, len(compressed)))
        blocks.append(compressed)
        offset += len(compressed)
    return bytes(directory) + b"".join(blocks), len(directory)


def directory_records(reader):
    count, = HEADER.unpack(reader.read(HEADER.size))
    raw = reader.read(count * DIRECTORY_ROW.size)
    if len(raw) != count * DIRECTORY_ROW.size:
        raise ValueError("Short block directory")
    return tuple(DIRECTORY_ROW.iter_unpack(raw))


def find(read_row, count, key):
    lower, upper = 0, count
    while lower < upper:
        middle = (lower + upper) // 2
        record = read_row(middle)
        actual = record[:KEY_SIZE]
        if actual == key:
            return record
        if actual < key:
            lower = middle + 1
        else:
            upper = middle
    return None


def in_memory(data, key):
    def row(index):
        start = index * ROW_SIZE
        return data[start:start + ROW_SIZE]

    return find(row, len(data) // ROW_SIZE, key)


def lookup(reader, layout, query, retain):
    if not layout.codec:
        def row(index):
            reader.seek(index * ROW_SIZE)
            return reader.read(ROW_SIZE)
        return [find(row, ROWS, key) for key in query]

    codec = CODECS[layout.codec]
    if not layout.block_rows:
        if retain:
            data = codec.decompress(reader.read())
            return [in_memory(data, key) for key in query]
        results = []
        for key in query:
            reader.seek(0)
            results.append(in_memory(codec.decompress(reader.read()), key))
        return results

    records = directory_records(reader)
    starts = tuple(key for key, _, _ in records)
    results = []
    for key in query:
        which = bisect_right(starts, key) - 1
        if which < 0:
            results.append(None)
            continue
        _, offset, size = records[which]
        reader.seek(offset)
        data = codec.decompress(reader.read(size))
        results.append(in_memory(data, key))
    return results


def scan_stream(reader, digest):
    for block in iter(lambda: reader.read(SCAN_ROWS * ROW_SIZE), b""):
        digest.update(block)


def scan(reader, layout):
    digest = sha256()
    if not layout.codec:
        scan_stream(reader, digest)
    elif not layout.block_rows:
        with CODECS[layout.codec].open_stream(reader) as stream:
            scan_stream(stream, digest)
    else:
        records = directory_records(reader)
        codec = CODECS[layout.codec]
        for _, offset, size in records:
            reader.seek(offset)
            digest.update(codec.decompress(reader.read(size)))
    return digest.hexdigest()


def assess(path, layout, mode, query, expected_rows, expected_scan):
    with path.open("rb", buffering=0) as file:
        reader = CountingReader(file)
        if mode == "scan":
            result = scan(reader, layout)
            if result != expected_scan:
                raise ValueError((layout, result, expected_scan))
        else:
            result = lookup(reader, layout, query, retain=mode == "lookup-retained")
            if result != expected_rows:
                raise ValueError((layout, "lookup mismatch"))
        return reader.bytes


def benchmark(trials):
    ordered, query, by_key = make_fixture()
    expected_scan = sha256(ordered).hexdigest()
    expected_rows = [by_key.get(key) for key in query]
    layouts = [Layout("raw", "")]
    for codec in CODECS:
        layouts.append(Layout(f"{codec}-whole", codec))
        layouts.extend(Layout(f"{codec}-block-{rows}", codec, rows) for rows in BLOCK_ROWS)

    implementations = {}
    measured = []
    with TemporaryDirectory(prefix="llmlang-index-compression-") as temp:
        root = Path(temp)
        tasks = []
        for layout in layouts:
            artifact, directory_size = encode(layout, ordered)
            path = root / layout.name
            path.write_bytes(artifact)
            implementations[layout.name] = {
                "artifact_bytes": len(artifact), "directory_bytes": directory_size,
                "artifact_sha256": sha256(artifact).hexdigest(), "operations": {},
            }
            modes = ["lookup-fresh", "scan"]
            if layout.codec and not layout.block_rows:
                modes.append("lookup-retained")
            for mode in modes:
                tasks.append((path, layout, mode))

        for path, layout, mode in tasks:
            args = (path, layout, mode, query, expected_rows, expected_scan)
            tracemalloc.start()
            try:
                logical_reads = assess(*args)
                peak = tracemalloc.get_traced_memory()[1]
            finally:
                tracemalloc.stop()
            implementations[layout.name]["operations"][mode] = {"read_bytes": logical_reads}
            measured.append({"trial": "trace", "layout": layout.name, "operation": mode,
                             "read_bytes": logical_reads, "elapsed_ns": "", "python_peak_bytes": peak})

        rng = Random(214)
        for trial in range(1, trials + 1):
            rng.shuffle(tasks)
            for path, layout, mode in tasks:
                start = perf_counter_ns()
                logical_reads = assess(path, layout, mode, query, expected_rows, expected_scan)
                elapsed = perf_counter_ns() - start
                if logical_reads != implementations[layout.name]["operations"][mode]["read_bytes"]:
                    raise ValueError("Read count changed across trials")
                measured.append({"trial": trial, "layout": layout.name, "operation": mode,
                                 "read_bytes": logical_reads, "elapsed_ns": elapsed,
                                 "python_peak_bytes": ""})
    return ({
        "python": platform.python_version(), "system": platform.system(),
        "machine": platform.machine(), "zlib": zlib.ZLIB_RUNTIME_VERSION,
        "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "fixture": {"rows": ROWS, "row_bytes": ROW_SIZE, "query_count": len(query),
                    "lookup_hits": sum(row is not None for row in expected_rows),
                    "logical_sha256": expected_scan,
                    "queries_sha256": sha256(b"".join(query)).hexdigest()},
        "layouts": implementations,
    }, measured)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=7)
    parser.add_argument("--measurements", type=Path, required=True)
    args = parser.parse_args()
    if args.trials < 0:
        parser.error("--trials must be nonnegative")
    evidence, measured = benchmark(args.trials)
    with args.measurements.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=tuple(measured[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(measured)
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
