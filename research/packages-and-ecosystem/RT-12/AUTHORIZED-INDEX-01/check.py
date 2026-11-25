"""Verify signed sparse projection authority and exact recovery in a local fixture."""

import argparse
from collections import Counter
from dataclasses import replace
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import platform
import re
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
SPARSE = HERE.parent / "INDEX-INTEGRITY-01" / "sparse.py"
SIGNING = HERE.parents[3] / "research" / "security" / "RT-16" / "BUILD-ATTESTATION-01" / "run.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


S = load_module("authorized_index_sparse", SPARSE)
SIGN = load_module("authorized_index_signing", SIGNING)


def authenticate(openssl, temp, statement, authority, expected):
    if statement is None:
        return None
    payload = json.loads(statement.payload)
    if any(payload.get(name) != value for name, value in expected.items()):
        return None
    message = temp / "projection-payload"
    signature = temp / "projection-signature"
    message.write_bytes(statement.payload)
    signature.write_bytes(statement.signature)
    result = SIGN.execute([openssl, "pkeyutl", "-verify", "-rawin", "-pubin", "-inkey",
                           str(authority), "-in", str(message), "-sigfile", str(signature)],
                          temp, check=False)
    if result.returncode:
        return None
    codec, rows, directory = (payload.get(field) for field in ("codec", "block_rows", "directory_sha256"))
    if (codec, rows) not in (("gzip", 64), ("bzip2", 32)):
        return None
    if not isinstance(directory, str) or re.fullmatch(r"[0-9a-f]{64}", directory) is None:
        return None
    return S.Pin(codec, rows, bytes.fromhex(payload["logical_sha256"]), bytes.fromhex(directory))


def read(view, pin, key):
    if pin is None:
        return ("unavailable", None, "unauthorized")
    try:
        return S.resolve(view, pin, key, anchored=True, recover=True)
    except ValueError:
        return ("unavailable", None, "incompatible-rebuild")


def run(openssl, temp):
    canonical, _, oracle = S.make_fixture()
    keys = sorted(oracle)
    pin, index = S.create_projection(canonical, "gzip", 64)
    alternate_pin, alternate = S.create_projection(canonical, "bzip2", 32)
    assert pin.logical_sha256 == alternate_pin.logical_sha256
    assert pin.directory_sha256 != alternate_pin.directory_sha256

    authority_key, authority_public = SIGN.keys(openssl, temp, "projection-authority")
    unrelated_key, _ = SIGN.keys(openssl, temp, "unrelated-publisher")
    scope = {"type": "package-index-projection:v1", "package": "fixture-package",
             "snapshot": "fixture-snapshot-3", "table": "objects", "authority_generation": 3,
             "logical_sha256": pin.logical_sha256.hex()}
    claims = {**scope, "codec": pin.codec, "block_rows": pin.block_rows,
              "directory_sha256": pin.directory_sha256.hex()}
    valid = SIGN.sign(openssl, temp, authority_key, claims)

    def signed(**override):
        return SIGN.sign(openssl, temp, authority_key, {**claims, **override})

    rows = {
        "authorized": (index, valid, "sparse"),
        "missing_directory": (replace(index, directory=None), valid, "rebuilt"),
        "corrupt_directory": (replace(index, directory=replace(index.directory, payload=b"damaged")),
                              valid, "rebuilt"),
        "alternate_under_original_pin": (alternate, valid, "rebuilt"),
        "alternate_under_own_pin": (
            alternate, signed(codec=alternate_pin.codec, block_rows=alternate_pin.block_rows,
                              directory_sha256=alternate_pin.directory_sha256.hex()), "sparse"),
        "lost_directory_and_canonical": (replace(index, directory=None, canonical=None), valid, "refused"),
        "lost_directory_and_wrong_canonical": (replace(index, directory=None, canonical=b"unrelated"),
                                               valid, "refused"),
        "unknown_key": (index, SIGN.sign(openssl, temp, unrelated_key, claims), "unauthorized"),
        "wrong_package": (index, signed(package="other-fixture"), "unauthorized"),
        "stale_snapshot": (index, signed(snapshot="fixture-snapshot-2"), "unauthorized"),
        "wrong_table": (index, signed(table="exports"), "unauthorized"),
        "revoked_generation": (index, signed(authority_generation=2), "unauthorized"),
        "wrong_logical_digest": (index, signed(logical_sha256="00" * 32), "unauthorized"),
        "unknown_statement_type": (index, signed(type="other-record:v1"), "unauthorized"),
        "unsupported_layout": (index, signed(codec="unknown"), "unauthorized"),
        "invalid_directory_digest": (index, signed(directory_sha256="invalid"), "unauthorized"),
        "absent_authority_record": (index, None, "unauthorized"),
        "inconsistent_signed_layout": (index, signed(directory_sha256="00" * 32), "incompatible-rebuild"),
    }

    probes = (keys[10], keys[4097], bytes([255]) * S.KEY_SIZE)
    counts = Counter()
    evidence = {}
    for name, (view, statement, expected_route) in rows.items():
        admitted = authenticate(openssl, temp, statement, authority_public, scope)
        outcomes = []
        for key in probes:
            actual = read(view, admitted, key)
            payload = oracle.get(key)
            expected = (("found", sha256(payload).hexdigest()) if payload is not None else ("missing", None))
            if expected_route not in ("sparse", "rebuilt"):
                expected = ("unavailable", None)
            assert actual == (*expected, expected_route), (name, actual)
            counts[expected_route] += 1
            outcomes.append(actual)
        evidence[name] = outcomes
    return {"python": platform.python_version(),
            "openssl": SIGN.execute([openssl, "version"], temp).stdout.strip(),
            "counts": dict(counts), "rows": evidence, "scope": scope,
            "directory_sha256": [pin.directory_sha256.hex(), alternate_pin.directory_sha256.hex()],
            "sources": {"check.py": sha256(Path(__file__).read_bytes()).hexdigest(),
                        "sparse.py": sha256(SPARSE.read_bytes()).hexdigest(),
                        "signing": sha256(SIGNING.read_bytes()).hexdigest()}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--openssl", default="openssl")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="rt12-authorized-index-") as temporary:
        print(json.dumps(run(args.openssl, Path(temporary)), indent=2, sort_keys=True))
