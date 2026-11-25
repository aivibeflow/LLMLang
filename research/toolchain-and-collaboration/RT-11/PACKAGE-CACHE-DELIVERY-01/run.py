#!/usr/bin/env python3
"""Measure package-cache delivery for five exact result families."""

from copy import deepcopy
import json
from pathlib import Path
import runpy
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZIP_STORED, ZipFile, ZipInfo

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parents[2]
RT12 = RESEARCH / "packages-and-ecosystem/RT-12"
OPTIONAL = runpy.run_path(str(RT12 / "OPTIONAL-ACTION-CACHE-01/run.py"))
NATIVE = runpy.run_path(str(HERE.parent / "TYPED-ACTION-RECEIPTS-01/run.py"))
STATIC = OPTIONAL["STATIC"]
PACKAGE_MEMBER = OPTIONAL["CORE"]
INDEX_MEMBER = OPTIONAL["INDEX"]
FAMILIES = ("validate", "compile", "analyze", "test", "proof")
LAYOUTS = {
    "bare": (False, False, False),
    "all-embedded": (True, True, True),
    "embedded-index": (True, True, False),
    "embedded-results": (True, False, True),
    "fully-detached": (True, False, False),
}


def result_artifacts(root, work, core_identity):
    native = NATIVE["Fixture"](work)
    request, receipt = native.compile("body", "int model(int x) { return x + 1; }\n")
    body = NATIVE["retrieve"](request, receipt)
    driver_request, driver_receipt = native.compile("driver", NATIVE["DRIVER"])
    driver = NATIVE["retrieve"](driver_request, driver_receipt)
    link_request, link_receipt = native.link(driver, body)
    program = NATIVE["retrieve"](link_request, link_receipt)
    test_request, test_receipt = native.test(program, [-3, 0, 9], 1)
    proof_request, proof_receipt = native.proof(program, 1, 9, 10)
    symbols = subprocess.run(
        ["readelf", "--wide", "--syms", "body.o"], cwd=work, text=True,
        capture_output=True, check=True,
    ).stdout
    assert [line.split()[-1] for line in symbols.splitlines() if " FUNC " in line] == ["model"]
    encode = OPTIONAL["json_bytes"]
    sha = OPTIONAL["sha"]
    payloads = {
        "validate": (sha(core_identity["core_archive"].encode()), encode(core_identity)),
        "compile": ("sha256:" + request.address(), body.payload),
        "analyze": ("sha256:" + body.address, symbols.encode()),
        "test": ("sha256:" + test_request.address(), NATIVE["retrieve"](test_request, test_receipt).payload),
        "proof": ("sha256:" + proof_request.address(), NATIVE["retrieve"](proof_request, proof_receipt).payload),
    }
    records = {
        family: OPTIONAL["sample_record"](
            action_kind=family, input_hashes=[root, subject], output_artifacts=[sha(payload)]
        )
        for family, (subject, payload) in payloads.items()
    }
    assert len({record["action_key"] for record in records.values()}) == len(FAMILIES)
    return records, {OPTIONAL["sha"](payload): payload for _, payload in payloads.values()}


def write_delivery(path, core, index, payloads, layout):
    has_cache, inline_index, inline_results = layout
    path.mkdir()
    cas = path / "cas"
    cas.mkdir()
    with ZipFile(path / "package.zip", "w", compression=ZIP_STORED) as archive:
        archive.writestr(ZipInfo(PACKAGE_MEMBER), core)
        if has_cache and inline_index:
            archive.writestr(ZipInfo(INDEX_MEMBER), index)
        if has_cache and inline_results:
            for address, payload in sorted(payloads.items()):
                archive.writestr(ZipInfo(OPTIONAL["artifact_path"](address)), payload)
    if has_cache and not inline_index:
        (path / "index.json").write_bytes(index)
    if has_cache and not inline_results:
        for address, payload in payloads.items():
            (cas / address.split(":", 1)[1]).write_bytes(payload)


def read_delivery(path, work, demand, requests, trusted, online):
    counts = {"detached_reads": 0, "detached_bytes": 0}
    expected_shape = {
        family: request["action_key"] for family, request in requests.items()
    }

    def fetch(filename):
        if not online or not filename.is_file():
            return None
        data = filename.read_bytes()
        counts["detached_reads"] += 1
        counts["detached_bytes"] += len(data)
        return data

    package_path = path / "package.zip"
    counts["initial_download_bytes"] = package_path.stat().st_size
    with ZipFile(package_path) as package:
        names = package.namelist()
        assert len(names) == len(set(names))
        core_identity = OPTIONAL["checked_core"](package.read(PACKAGE_MEMBER), work)
        assert core_identity is not None
        if not demand:
            return core_identity, {}, dict(counts)
        if INDEX_MEMBER in names:
            index = package.read(INDEX_MEMBER)
        else:
            index = fetch(path / "index.json")
        if index is None:
            return core_identity, dict.fromkeys(demand, "index-unavailable"), dict(counts)
        try:
            data = json.loads(index)
            if not isinstance(data, dict):
                raise ValueError("cache index must be an object")
            normalized = OPTIONAL["validate_cache_index"](data, OPTIONAL["COMPONENTS"])
        except (ValueError, OPTIONAL["PackageFormatError"]):
            return core_identity, dict.fromkeys(demand, "index-refused"), dict(counts)
        rows = {row["action_key"]: row for row in normalized["records"]}
        by_family = {}
        for family in demand:
            action_key = expected_shape[family]
            row = rows.get(action_key)
            if row is None:
                by_family[family] = "action-miss"
                continue
            addresses = row["output_artifacts"]
            if (row["action_kind"] != family or row["status"] != "success"
                    or trusted.get(action_key) != addresses):
                by_family[family] = "receipt-refused"
                continue
            address, = addresses
            member = OPTIONAL["artifact_path"](address)
            payload = package.read(member) if member in names else fetch(path / "cas" / address.split(":", 1)[1])
            if payload is None:
                by_family[family] = "result-unavailable"
                continue
            if OPTIONAL["sha"](payload) != address:
                by_family[family] = "digest-refused"
                continue
            by_family[family] = "hit"
    return core_identity, by_family, dict(counts)


def experiment(directory):
    core_path = directory / "base.llpkg"
    STATIC["static_archive"](core_path, STATIC["sample_index"]())
    core = core_path.read_bytes()
    identity = OPTIONAL["checked_core"](core, directory)
    root = identity["package_root"]
    records, payloads = result_artifacts(root, directory, identity)
    trusted = {record["action_key"]: record["output_artifacts"] for record in records.values()}
    index = OPTIONAL["encode_index"](*records.values())
    profiles = {
        "package-only": ((), True),
        "compile-only": (("compile",), True),
        "all-online": (FAMILIES, True),
        "all-offline": (FAMILIES, False),
    }
    measurements = []
    for name, layout in LAYOUTS.items():
        path = directory / name
        write_delivery(path, core, index, payloads, layout)
        for profile, (demand, online) in profiles.items():
            verified_identity, results, metric = read_delivery(path, directory, demand, records, trusted, online)
            assert verified_identity == identity
            if name == "bare" or (not online and not layout[1]):
                expected = "index-unavailable"
            elif not online and not layout[2]:
                expected = "result-unavailable"
            else:
                expected = "hit"
            assert results == dict.fromkeys(demand, expected)
            measurements.append({
                "layout": name, "profile": profile, **metric, "results": results,
            })

    faults = []
    for family, request in records.items():
        address, = request["output_artifacts"]
        corrupt = payloads | {address: b"corrupted result\n"}
        path = directory / ("corrupt-" + family)
        write_delivery(path, core, index, corrupt, LAYOUTS["fully-detached"])
        verified_identity, results, metric = read_delivery(path, directory, FAMILIES, records, trusted, True)
        assert verified_identity == identity
        assert results == (dict.fromkeys(FAMILIES, "hit") | {family: "digest-refused"})
        faults.append({"family": family, "control": "corruption", "results": results, **metric})

        alternative_kind = next(kind for kind in FAMILIES if kind != family)
        wrong, = records[alternative_kind]["output_artifacts"]
        wrong_record = deepcopy(request) | {"output_artifacts": [wrong]}
        modified = records | {family: wrong_record}
        path = directory / ("wrong-" + family)
        write_delivery(
            path, core, OPTIONAL["encode_index"](*modified.values()), payloads, LAYOUTS["fully-detached"]
        )
        verified_identity, results, metric = read_delivery(path, directory, FAMILIES, records, trusted, True)
        assert verified_identity == identity
        assert results == (dict.fromkeys(FAMILIES, "hit") | {family: "receipt-refused"})
        assert metric["detached_reads"] == len(FAMILIES)
        faults.append({"family": family, "control": "cross-family", "results": results, **metric})

    return {
        "format": "package-cache-delivery-01",
        "core_identity": identity, "index_bytes": len(index),
        "families": {
            family: {
                "action_key": row["action_key"], "artifact": row["output_artifacts"][0],
                "bytes": len(payloads[row["output_artifacts"][0]]),
            }
            for family, row in records.items()
        },
        "measurements": measurements, "faults": faults,
    }


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-cache-delivery-") as work:
        ledger = experiment(Path(work))
    content = json.dumps(ledger, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(content, encoding="utf-8")
    else:
        print(content, end="")
