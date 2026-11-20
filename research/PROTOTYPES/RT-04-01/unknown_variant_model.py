"""Finite policies for a consumer relaying an unknown wire enum case."""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any


class UnknownCasePolicy(Enum):
    REJECT = "reject"
    FALLBACK = "fallback"
    PRESERVE = "preserve"


@dataclass(frozen=True)
class KnownState:
    kind: str
    fields: dict[str, Any]


@dataclass(frozen=True)
class OpaqueState:
    fields: dict[str, Any]


@dataclass(frozen=True)
class DecodeError:
    reason: str


State = KnownState | OpaqueState


def decode_v1(payload: bytes, policy: UnknownCasePolicy) -> State | DecodeError:
    try:
        obj: Any = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        return DecodeError(f"invalid JSON: {error}")
    if not isinstance(obj, dict) or not isinstance(obj.get("state"), dict):
        return DecodeError("state must be an object")

    state = obj["state"]
    kind = state.get("kind")
    if not isinstance(kind, str):
        return DecodeError("state.kind must be a string")
    if kind == "ready":
        if set(state) != {"kind"}:
            return DecodeError("ready carries no fields")
        return KnownState(kind, {})
    if kind == "failed":
        code = state.get("code")
        if not isinstance(code, int) or isinstance(code, bool):
            return DecodeError("failed.code must be an integer")
        if set(state) != {"kind", "code"}:
            return DecodeError("failed contains unexpected fields")
        return KnownState(kind, {"code": code})
    if policy is UnknownCasePolicy.REJECT:
        return DecodeError(f"unknown state case: {kind}")
    if policy is UnknownCasePolicy.FALLBACK:
        return KnownState("other", {})
    # Retain the complete JSON object so an older relay can forward it.
    return OpaqueState(dict(state))


def encode_state(state: State) -> bytes:
    if isinstance(state, OpaqueState):
        obj = {"state": state.fields}
    else:
        obj = {"state": {"kind": state.kind, **state.fields}}
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
