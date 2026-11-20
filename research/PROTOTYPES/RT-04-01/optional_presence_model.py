"""Finite encodings for absent, null, value, and decode-failure states.

The JSON adapter is a deliberately small RT-04 research fixture. It does not
implement a language serializer or select an LLMLang representation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any


class Presence(Enum):
    ABSENT = "absent"
    NULL = "null"
    VALUE = "value"


@dataclass(frozen=True)
class FieldState:
    presence: Presence
    value: Any = None

    def __post_init__(self) -> None:
        if self.presence is Presence.VALUE and self.value is None:
            raise ValueError("a value case cannot contain JSON null")
        if self.presence is not Presence.VALUE and self.value is not None:
            raise ValueError("absent/null cases cannot carry a payload")


@dataclass(frozen=True)
class DecodeFailure:
    message: str


class UninitializedRead(ValueError):
    """An uninitialized local is not a value-level absence constructor."""


def decode_integer_field(document: bytes, key: str = "value") -> FieldState | DecodeFailure:
    """Decode one optional integer field from a minimal JSON object."""
    try:
        obj = json.loads(document)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        return DecodeFailure(f"invalid JSON: {error}")
    if not isinstance(obj, dict):
        return DecodeFailure("top-level JSON value must be an object")
    if key not in obj:
        return FieldState(Presence.ABSENT)
    value = obj[key]
    if value is None:
        return FieldState(Presence.NULL)
    # bool is a subclass of int in Python, but is not an integer JSON payload
    # for this experiment's declared `Int` field.
    if not isinstance(value, int) or isinstance(value, bool):
        return DecodeFailure("field value must be an integer or null")
    return FieldState(Presence.VALUE, value)


def encode_optional(state: FieldState) -> tuple[str, Any]:
    """One-level Option<T>; the chosen boundary policy collapses absent/null."""
    if state.presence in {Presence.ABSENT, Presence.NULL}:
        return ("none", None)
    return ("some", state.value)


def encode_nested_optional(state: FieldState) -> tuple[str, Any]:
    """Two-level Option<Option<T>> with an explicit absent/null convention."""
    if state.presence is Presence.ABSENT:
        return ("none", None)
    if state.presence is Presence.NULL:
        return ("some", ("none", None))
    return ("some", ("some", state.value))


def encode_presence_nullable(state: FieldState) -> tuple[bool, int | None]:
    """Presence bit plus nullable payload; preserves the three input states."""
    if state.presence is Presence.ABSENT:
        return (False, None)
    if state.presence is Presence.NULL:
        return (True, None)
    return (True, state.value)


def encode_result_presence(result: FieldState | DecodeFailure) -> tuple[str, Any]:
    """Result<Presence<Int>, DecodeError> keeps malformed input out of Option."""
    if isinstance(result, DecodeFailure):
        return ("error", result.message)
    return ("ok", encode_nested_optional(result))


def encode_json_field(state: FieldState, key: str = "value") -> bytes:
    """Serialize using absent=>omit, null=>explicit null, value=>JSON integer."""
    if state.presence is Presence.ABSENT:
        obj: dict[str, Any] = {}
    elif state.presence is Presence.NULL:
        obj = {key: None}
    else:
        obj = {key: state.value}
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def read_uninitialized() -> FieldState:
    raise UninitializedRead("read before initialization is a distinct error")
