"""Experimental composite language-version and registry helpers."""
from __future__ import annotations
import hashlib, re, tomllib

_COMPONENT_ID = re.compile(r"^[a-z][a-z0-9_]*$")

class LanguageVersionError(ValueError):
    pass

def load_component_registry(raw: bytes) -> tuple[str, ...]:
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise LanguageVersionError(str(exc)) from exc
    if set(data) != {"components"}:
        raise LanguageVersionError("registry must contain only the components key")
    components = data["components"]
    if not isinstance(components, list) or not components:
        raise LanguageVersionError("components must be a non-empty array")
    if not all(isinstance(x, str) and _COMPONENT_ID.fullmatch(x) for x in components):
        raise LanguageVersionError("invalid component identifier")
    if len(set(components)) != len(components):
        raise LanguageVersionError("duplicate component identifier")
    return tuple(components)

def registry_digest(components: tuple[str, ...]) -> str:
    payload = b"LLMLANG\0language-component-registry\0"
    for component in components:
        encoded = component.encode("ascii")
        payload += len(encoded).to_bytes(4, "big") + encoded
    return "sha256:" + hashlib.sha256(payload).hexdigest()

def parse_language_version(value: str, components: tuple[str, ...]) -> tuple[int, ...]:
    if not isinstance(value, str) or not value:
        raise LanguageVersionError("language version must be a non-empty string")
    parts = value.split(".")
    if len(parts) > len(components):
        raise LanguageVersionError("language version has more coordinates than the registry")
    if any(not re.fullmatch(r"0|[1-9][0-9]*", part) for part in parts):
        raise LanguageVersionError("version coordinates must be canonical non-negative integers")
    numbers = tuple(int(part) for part in parts)
    return numbers + (0,) * (len(components) - len(numbers))

def validate_registry_extension(previous: tuple[str, ...], current: tuple[str, ...]) -> None:
    if len(current) < len(previous) or current[:len(previous)] != previous:
        raise LanguageVersionError("component registry is not an append-only extension")
    if len(set(current)) != len(current):
        raise LanguageVersionError("duplicate component identifier")
