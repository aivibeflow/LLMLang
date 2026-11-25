"""Repeat the archived serial benchmark with an independent LZ4 block per record."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import lz4
import lz4.block

import record_codecs
import run
import single_file


ENCODINGS = ("jsonl", "json-seq", "cbor", "protobuf", "flatbuffers")
LZ4_PROFILES = tuple(f"{encoding}-lz4" for encoding in ENCODINGS)
CONTROLS = ("cbor", "cbor-zlib")
PROFILES = LZ4_PROFILES + CONTROLS
MAX_RECORD_BYTES = 4096


def serialize(profile, value):
    if profile in CONTROLS:
        return record_codecs.serialize(profile, value)
    data = record_codecs.serialize(profile.removesuffix("-lz4"), value)
    if not 1 <= len(data) <= MAX_RECORD_BYTES:
        raise ValueError("out-of-profile uncompressed record size")
    return lz4.block.compress(data, mode="fast", acceleration=1, store_size=True)


def deserialize(profile, data):
    if profile in CONTROLS:
        return record_codecs.deserialize(profile, data)
    size = int.from_bytes(data[:4], "little")
    if len(data) < 5 or not 1 <= size <= MAX_RECORD_BYTES:
        raise ValueError("invalid LZ4 block size prefix")
    unpacked = lz4.block.decompress(data)
    if len(unpacked) != size:
        raise ValueError("LZ4 block size mismatch")
    return record_codecs.deserialize(profile.removesuffix("-lz4"), unpacked)


def write_evidence(path, evidence):
    path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--objects", type=int, default=100_000)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--seed", type=int, default=27001)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--ranges-output", type=Path)
    args = parser.parse_args()
    if not (160 <= args.objects < 1 << 31) or args.repeats < 1:
        parser.error("require at least 160 records and one repetition")

    # Keep archived source bytes and ledger digests intact. Both archived test
    # paths resolve their record codec through these two functions in run.py.
    run.serialize, run.deserialize = serialize, deserialize
    args.profiles = PROFILES
    with TemporaryDirectory(prefix="spg-lz4-benchmark-") as temp:
        evidence = run.run(args, Path(temp))
    adapter_hash = sha256(Path(__file__).read_bytes()).hexdigest()
    evidence["lz4"] = {
        "adapter_sha256": adapter_hash,
        "package": version("lz4"),
        "library": lz4.library_version_string(),
        "mode": "fast",
        "acceleration": 1,
        "framing": "raw block with four-byte little-endian original length",
        "max_decoded_record_bytes": MAX_RECORD_BYTES,
    }
    write_evidence(args.output, evidence)
    if args.ranges_output:
        single_file.PROFILES = PROFILES
        sys.argv = [sys.argv[0], "--evidence", str(args.output),
                    "--output", str(args.ranges_output)]
        single_file.main()
        ranges = json.loads(args.ranges_output.read_text(encoding="utf-8"))
        ranges["lz4_adapter_sha256"] = adapter_hash
        write_evidence(args.ranges_output, ranges)


if __name__ == "__main__":
    main()
