"""Reconcile exact-build, signed restoration and signed package delivery evidence."""

from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PINS = {
    "security/RT-16/BUILD-ATTESTATION-01": "f406ebdf2215eb7390b5b70f4677ffd31ad396a8a2f74f4053c0e51b3ee79d8f",
    "toolchain-and-collaboration/RT-11/SIGNED-REBUILD-ADMISSION-01": "a50fbd3d3068b82867a5e8e8c13da6b6c2bf8583f120c208e13edb697d9a218c",
    "packages-and-ecosystem/RT-12/DECLARED-PACKAGE-RIGHTS-01": "96cd6a2a14deed87811b3c01107bf6630947e84068ac4d3ad88d02cb499f5611",
}


def read(name):
    source = (ROOT / name / "evidence.json").read_bytes()
    assert sha256(source).hexdigest() == PINS[name]
    return json.loads(source)


def collect():
    build, cache, package = [read(name) for name in PINS]
    reproducibility = build["native_reproducibility"]
    independent = reproducibility["independent-checkout-b"]
    assert independent["same_artifact"] and independent["same_recipe"]
    for fixture in ("comment-only", "unused-flag"):
        assert reproducibility[fixture]["same_artifact"] and not reproducibility[fixture]["same_recipe"]
    claims = list(build["admissions"].values())
    subject, exact = (sum(claim[rule] for claim in claims)
                      for rule in ("signed_subject_only", "exact_signed_predicate"))
    assert (len(claims), subject, exact) == (10, 6, 2)
    cases = {row["name"]: row["decision"] for row in cache["rows"]}
    controls = {name: cases[name] for name in ("conflict-with-missing-alternative", "explicit-revocation",
                                              "wrong-bytes", "no-independent-rebuild",
                                              "signed-disagrees-with-rebuild")}
    assert controls == {"conflict-with-missing-alternative": "conflict", "explicit-revocation": "exact-hit",
                        "wrong-bytes": "payload-refused", "no-independent-rebuild": "rebuild-unavailable",
                        "signed-disagrees-with-rebuild": "rebuild-disagrees"}
    assert (len(cases), cache["candidate_orders"], cache["exact_rebuilds"]) == (18, 120, 3)
    repacking = package["repacking_controls"]
    assert repacking == {"old_publication_applies_after_repacking": False,
                         "fresh_publication_applies_after_repacking": True,
                         "declared_use_preserved_across_physical_repacking": True,
                         "declared_use_after_logical_change": False}
    return {"inputs": PINS, "build_profiles": len(reproducibility), "signed_subject_admissions": subject,
            "signed_exact_recipe_admissions": exact, "cache_controls": controls,
            "candidate_orders": cache["candidate_orders"], "exact_rebuilds": cache["exact_rebuilds"],
            "package_repacking": repacking, "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(collect(), sort_keys=True, indent=2))
