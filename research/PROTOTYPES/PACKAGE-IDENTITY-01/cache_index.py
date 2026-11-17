"""Experimental cache-index record validation; not a normative wire format."""
from __future__ import annotations
from typing import Any
from package_identity import PackageFormatError, digest, parse_hash
from language_version import LanguageVersionError, parse_language_version

CACHE_SCHEMA = "llmlang.cache-index"
CACHE_SCHEMA_VERSION = 1
RECORD_KEYS = {
    "action_key", "action_kind", "action_implementation", "input_hashes",
    "language_version", "language_component_registry_digest", "toolchain_identity",
    "target_profile_digest", "configuration_digest", "runtime_identity",
    "status", "determinism", "dependency_complete", "output_artifacts",
}
CACHEABLE_STATUSES = {"success", "rejected"}
DETERMINISM_CLASSES = {"byte_deterministic", "semantic_deterministic"}

def _required_hash(value: Any, field: str) -> None:
    if not isinstance(value, str):
        raise PackageFormatError(f"{field} must be a content hash")
    parse_hash(value)

def action_key_projection(record: dict[str, Any]) -> dict[str, Any]:
    return {key: record[key] for key in (
        "action_kind", "action_implementation", "input_hashes",
        "language_version", "language_component_registry_digest", "toolchain_identity",
        "target_profile_digest", "configuration_digest", "runtime_identity",
    )}

def expected_action_key(record: dict[str, Any]) -> str:
    return digest("action-key.candidate.v1", action_key_projection(record))

def validate_cache_index(data: dict[str, Any], components: tuple[str, ...]) -> dict[str, Any]:
    if set(data) != {"schema", "schema_version", "records"}:
        raise PackageFormatError("cache index has unknown or missing top-level fields")
    if data["schema"] != CACHE_SCHEMA or data["schema_version"] != CACHE_SCHEMA_VERSION:
        raise PackageFormatError("unsupported cache index schema/version")
    records = data["records"]
    if not isinstance(records, list):
        raise PackageFormatError("cache index records must be an array")
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != RECORD_KEYS:
            raise PackageFormatError("cache record has unknown or missing fields")
        for field in ("action_key", "action_implementation", "language_component_registry_digest",
                      "toolchain_identity", "target_profile_digest", "configuration_digest",
                      "runtime_identity"):
            _required_hash(record[field], field)
        if not isinstance(record["action_kind"], str) or not record["action_kind"]:
            raise PackageFormatError("action_kind must be a non-empty string")
        inputs, outputs = record["input_hashes"], record["output_artifacts"]
        if not isinstance(inputs, list) or not all(isinstance(x, str) for x in inputs):
            raise PackageFormatError("input_hashes must be an array of content hashes")
        if len(set(inputs)) != len(inputs):
            raise PackageFormatError("duplicate input hash")
        for value in inputs:
            parse_hash(value)
        if not isinstance(outputs, list) or not all(isinstance(x, str) for x in outputs):
            raise PackageFormatError("output_artifacts must be an array of content hashes")
        for value in outputs:
            parse_hash(value)
        try:
            parse_language_version(record["language_version"], components)
        except LanguageVersionError as exc:
            raise PackageFormatError(str(exc)) from exc
        if record["status"] not in CACHEABLE_STATUSES:
            raise PackageFormatError("transient or unsupported action status is not cacheable")
        if record["determinism"] not in DETERMINISM_CLASSES:
            raise PackageFormatError("non-cacheable or unsupported determinism class")
        if record["dependency_complete"] is not True:
            raise PackageFormatError("incomplete dependency closure is not cacheable")
        key = record["action_key"]
        if key in seen:
            raise PackageFormatError("duplicate Action Key")
        seen.add(key)
        if expected_action_key(record) != key:
            raise PackageFormatError("Action Key does not match its declared inputs")
    if [r["action_key"] for r in records] != sorted(r["action_key"] for r in records):
        raise PackageFormatError("cache records must be sorted by Action Key")
    return data
