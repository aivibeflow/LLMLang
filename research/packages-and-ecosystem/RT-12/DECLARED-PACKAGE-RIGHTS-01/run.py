"""Separate native archive integrity, publisher authority, and declared-use policy."""

import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import importlib.util
from itertools import product
import json
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
STATIC = HERE.parent / "STATIC-INDEX-01" / "run.py"
SIGNING = ROOT / "research/security/RT-16/BUILD-ATTESTATION-01/run.py"


def import_fixture(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ARCHIVE = import_fixture("package_static_fixture", STATIC)
SIGN = import_fixture("package_signing_fixture", SIGNING)
POLICY = 7
NOW = 12
REQUESTER = "evaluation-team"
USE = "internal-evaluation"


def inspect(path):
    frozen = path.read_bytes()
    with TemporaryDirectory(prefix="llmlang-rights-view-") as scratch:
        copy = Path(scratch) / "checked.llpkg"
        copy.write_bytes(frozen)
        try:
            root, _ = ARCHIVE.render(copy)
        except ARCHIVE.ArchiveError:
            return None
    return {"package_root": root, "archive_sha256": sha256(frozen).hexdigest()}


def verify_signature(openssl, work, public_keys, envelope):
    if envelope is None:
        return None
    payload = json.loads(envelope.payload)
    current_key = public_keys.get(payload["signer"])
    if current_key is None:
        return None
    data, signature = work / "verify-data", work / "verify-signature"
    data.write_bytes(envelope.payload)
    signature.write_bytes(envelope.signature)
    result = SIGN.execute([openssl, "pkeyutl", "-verify", "-rawin", "-pubin", "-inkey", str(current_key),
                           "-in", str(data), "-sigfile", str(signature)], work, check=False)
    return payload if result.returncode == 0 else None


def fabricate(openssl, work, keys, claims):
    signed = {}
    for label, payload in claims.items():
        signed[label] = (SIGN.sign(openssl, work, keys[payload["signer"]], payload)
                         if payload is not None else None)
    return signed


def publisher_binding(facts, signed):
    return (facts is not None and signed is not None
            and signed["kind"] == "publication"
            and signed["package_root"] == facts["package_root"]
            and signed["archive_sha256"] == facts["archive_sha256"])


def publisher_authorized(facts, signed):
    return (publisher_binding(facts, signed)
            and signed["signer"] == "publisher" and signed["policy"] == POLICY)


def allowed_use(facts, signed):
    return (facts is not None and signed is not None and signed["kind"] == "declared-use"
            and signed["signer"] == "rights-authority" and signed["policy"] == POLICY
            and signed["package_root"] == facts["package_root"]
            and signed["principal"] == REQUESTER and signed["use"] == USE
            and signed["valid_from"] <= NOW < signed["valid_until"])


def assess(openssl, work):
    base, mirror, corrupted = (work / name for name in ("base.llpkg", "mirror.llpkg", "damaged.llpkg"))
    index = ARCHIVE.sample_index()
    ARCHIVE.static_archive(base, index)
    shutil.copyfile(base, mirror)
    ARCHIVE.corrupt_payload(base, corrupted)
    deliveries = {"original": inspect(base), "mirror": inspect(mirror), "corrupted": inspect(corrupted)}

    relocated = work / "relocated.llpkg"
    ARCHIVE.static_archive(relocated, index, table_path="mirror/tables")
    different = work / "different-root.llpkg"
    changed_index = deepcopy(index)
    changed_index["exports"][0]["object_hash"] = ARCHIVE.H2
    ARCHIVE.static_archive(different, ARCHIVE.normalize(changed_index))
    relocated_facts = inspect(relocated)
    distinct_facts = inspect(different)
    base_facts = deliveries["original"]
    assert base_facts == deliveries["mirror"] and deliveries["corrupted"] is None
    assert relocated_facts["package_root"] == base_facts["package_root"]
    assert relocated_facts["archive_sha256"] != base_facts["archive_sha256"]
    assert distinct_facts["package_root"] != base_facts["package_root"]

    keys = {name: SIGN.keys(openssl, work, name)
            for name in ("publisher", "rights-authority", "mirror-node", "retired-publisher")}
    private = {name: item[0] for name, item in keys.items()}
    public = {name: item[1] for name, item in keys.items()}
    publication = {"kind": "publication", "signer": "publisher", "policy": POLICY, **base_facts}
    permission = {"kind": "declared-use", "signer": "rights-authority", "policy": POLICY,
                  "package_root": base_facts["package_root"], "principal": REQUESTER, "use": USE,
                  "valid_from": 10, "valid_until": 20}
    publications = fabricate(openssl, work, private, {
        "exact": publication,
        "wrong-root": {**publication, "package_root": distinct_facts["package_root"]},
        "wrong-archive": {**publication, "archive_sha256": relocated_facts["archive_sha256"]},
        "mirror-signer": {**publication, "signer": "mirror-node"},
        "retired-signer": {**publication, "signer": "retired-publisher"},
        "old-policy": {**publication, "policy": POLICY - 1},
        "absent": None,
    })
    publications["tampered"] = replace(publications["exact"],
                                       payload=SIGN.canonical({**publication, "policy": POLICY - 1}))
    permissions = fabricate(openssl, work, private, {
        "exact": permission,
        "wrong-root": {**permission, "package_root": distinct_facts["package_root"]},
        "wrong-principal": {**permission, "principal": "release-team"},
        "wrong-use": {**permission, "use": "republish"},
        "expired": {**permission, "valid_until": NOW},
        "old-policy": {**permission, "policy": POLICY - 1},
        "wrong-authority": {**permission, "signer": "publisher"},
        "absent": None,
    })
    verified_p = {name: verify_signature(openssl, work, public, statement)
                  for name, statement in publications.items()}
    verified_r = {name: verify_signature(openssl, work, public, statement)
                  for name, statement in permissions.items()}
    if {name for name, entry in verified_p.items() if entry is None} != {"tampered", "absent"}:
        raise AssertionError("Unexpected publisher signature validity")
    if {name for name, entry in verified_r.items() if entry is None} != {"absent"}:
        raise AssertionError("Unexpected rights signature validity")

    totals = Counter()
    for delivered, p_state, r_state in product(deliveries, publications, permissions):
        facts, publisher, rights = deliveries[delivered], verified_p[p_state], verified_r[r_state]
        expected = delivered in {"original", "mirror"} and p_state == r_state == "exact"
        rules = {
            "content_integrity": facts is not None,
            "integrity_and_signature": publisher_binding(facts, publisher),
            "integrity_and_publisher": publisher_authorized(facts, publisher),
            "exact_declared_use": publisher_authorized(facts, publisher) and allowed_use(facts, rights),
        }
        if rules["exact_declared_use"] != expected:
            raise AssertionError((delivered, p_state, r_state, rules, expected))
        totals["cases"] += 1
        for rule, accepted in rules.items():
            totals[f"{rule}_accepted"] += accepted
            totals[f"{rule}_overallowed"] += accepted and not expected

    republished = SIGN.sign(openssl, work, private["publisher"], {**publication, **relocated_facts})
    relocated_statement = verify_signature(openssl, work, public, republished)
    controls = {
        "old_publication_applies_after_repacking": publisher_authorized(relocated_facts, verified_p["exact"]),
        "fresh_publication_applies_after_repacking": publisher_authorized(relocated_facts, relocated_statement),
        "declared_use_preserved_across_physical_repacking": allowed_use(relocated_facts, verified_r["exact"]),
        "declared_use_after_logical_change": allowed_use(distinct_facts, verified_r["exact"]),
    }
    assert set(name for name, accepted in controls.items() if accepted) == {
        "fresh_publication_applies_after_repacking", "declared_use_preserved_across_physical_repacking",
    }
    sources = (HERE / "run.py", STATIC, SIGNING, ARCHIVE.PACKAGE_INDEX / "package_archive.py",
               ARCHIVE.PACKAGE_IDENTITY / "package_identity.py")
    return {
        "openssl": SIGN.execute([openssl, "version"], work).stdout.strip(),
        "counts": dict(sorted(totals.items())),
        "repacking_controls": controls,
        "packages": {"base": base_facts, "repacked": relocated_facts, "different": distinct_facts},
        "source_sha256": {path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest()
                          for path in sources},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--openssl", default="openssl")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-declared-package-rights-") as tmp:
        print(json.dumps(assess(args.openssl, Path(tmp)), indent=2))
