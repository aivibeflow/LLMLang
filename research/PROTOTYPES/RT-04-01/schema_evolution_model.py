"""Finite wire-schema evolution profiles for Scenario 110.

This fixture compares explicit compatibility policies; it is not a schema
standard or LLMLang serializer.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any


class UnknownFieldPolicy(Enum):
    REJECT = "reject"
    IGNORE = "ignore"


class NullPolicy(Enum):
    REJECT = "reject"
    TREAT_AS_ABSENT = "treat_as_absent"


@dataclass(frozen=True)
class DecodeError:
    reason: str


@dataclass(frozen=True)
class Config:
    count: int
    enabled: bool


def encode_v1(config: Config) -> bytes:
    return json.dumps({"count": config.count}, sort_keys=True, separators=(",", ":")).encode()


def encode_v2(config: Config) -> bytes:
    return json.dumps(
        {"count": config.count, "enabled": config.enabled},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def decode_v1(
    payload: bytes, unknown_fields: UnknownFieldPolicy = UnknownFieldPolicy.REJECT
) -> Config | DecodeError:
    return _decode(payload, version=1, unknown_fields=unknown_fields)


def decode_v2(
    payload: bytes,
    *,
    enabled_default: bool = False,
    unknown_fields: UnknownFieldPolicy = UnknownFieldPolicy.REJECT,
    null_policy: NullPolicy = NullPolicy.REJECT,
) -> Config | DecodeError:
    return _decode(
        payload,
        version=2,
        enabled_default=enabled_default,
        unknown_fields=unknown_fields,
        null_policy=null_policy,
    )


def _decode(
    payload: bytes,
    *,
    version: int,
    enabled_default: bool = False,
    unknown_fields: UnknownFieldPolicy,
    null_policy: NullPolicy = NullPolicy.REJECT,
) -> Config | DecodeError:
    try:
        obj: Any = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        return DecodeError(f"invalid JSON: {error}")
    if not isinstance(obj, dict):
        return DecodeError("top-level value must be an object")

    allowed = {"count"} if version == 1 else {"count", "enabled"}
    extras = set(obj) - allowed
    if extras and unknown_fields is UnknownFieldPolicy.REJECT:
        return DecodeError(f"unknown fields: {sorted(extras)}")
    count = obj.get("count")
    if not isinstance(count, int) or isinstance(count, bool):
        return DecodeError("count must be an integer")

    if version == 1:
        return Config(count, enabled_default)

    enabled = obj.get("enabled", enabled_default)
    if enabled is None and null_policy is NullPolicy.TREAT_AS_ABSENT:
        enabled = enabled_default
    if not isinstance(enabled, bool):
        return DecodeError("enabled must be a boolean")
    return Config(count, enabled)
