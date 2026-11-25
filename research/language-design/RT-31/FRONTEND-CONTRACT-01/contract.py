"""Versioned source envelopes and located diagnostics for the four RT-31 profiles."""
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "HYBRID-PROFILE-01"))
from replay import PROFILES, RepresentationError, compile_program, parse, render, validate_graph
from profiles import FrontendError, validate
from hybrid import HybridError

STRING_CHAR = re.compile(r'\\u[0-9a-fA-F]{4}|\\.|[^"\\]', re.S)


def digest(value):
    return sha256(value).hexdigest()


def canonical(term):
    validate(term)
    return json.dumps(term, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode()


@dataclass(frozen=True)
class Source:
    profile: str
    data: bytes

    @property
    def identity(self):
        return digest(self.data)


@dataclass(frozen=True)
class Location:
    start_byte: int
    end_byte: int
    line: int
    byte_column: int
    precision: str


@dataclass(frozen=True)
class Diagnostic:
    phase: str
    profile: str
    source_sha256: str
    message: str
    location: Location | None
    path: tuple


class Failed(ValueError):
    def __init__(self, diagnostic):
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic


@dataclass(frozen=True)
class FrontendOutput:
    source: Source
    normalized: bytes

    @property
    def normalized_digest(self):
        return digest(self.normalized)


@dataclass(frozen=True)
class Generated:
    source: Source
    origin_profile: str
    origin_sha256: str
    normalized_digest: str


def json_locations(text):
    """Index value spans by object key/array index, using the JSON decoder for leaves."""
    decoder = json.JSONDecoder()
    whitespace = re.compile(r"[ \t\r\n]*")
    spans = {}

    def skip(position):
        return whitespace.match(text, position).end()

    def scan(start, path):
        char = text[start]
        if char in "{[":
            ending = "}" if char == "{" else "]"
            position = skip(start + 1)
            index = 0
            while text[position] != ending:
                if char == "{":
                    key, key_end = decoder.raw_decode(text, position)
                    value_start = skip(skip(key_end) + 1)
                else:
                    key, value_start = index, position
                position = skip(scan(value_start, (*path, key)))
                if text[position] != ",":
                    break
                position = skip(position + 1)
                index += 1
            end = position + 1
        else:
            _, end = decoder.raw_decode(text, start)
        spans[path] = (start, end)
        return end

    # Require valid JSON before locating anything in the structured envelope.
    json.loads(text)
    scan(skip(0), ())
    return spans


def scalar_point(text, span, decoded_offset):
    start, end = span
    raw = text[start:end]
    if not raw.startswith('"'):
        return None
    decoded = json.loads(raw)
    parts = tuple(STRING_CHAR.finditer(raw, 1, len(raw) - 1))
    decoded_parts = "".join(json.loads('"' + match[0] + '"') for match in parts)
    # A pair of escaped UTF-16 surrogates can decode as one character.
    if decoded_parts != decoded or not 0 <= decoded_offset <= len(parts):
        return None
    if decoded_offset == len(parts):
        return end - 1, end - 1
    selected = parts[decoded_offset]
    return start + selected.start(), start + selected.end()


def location(text, start, end, precision):
    beginning = text.rfind("\n", 0, start) + 1
    return Location(len(text[:start].encode()), len(text[:end].encode()),
                    text.count("\n", 0, start) + 1, len(text[beginning:start].encode()), precision)


def report(source, phase, message, text="", span=None, path=(), precision="point"):
    coordinates = location(text, *span, precision) if span is not None else None
    return Failed(Diagnostic(phase, source.profile, source.identity, message, coordinates, tuple(path)))


def point(text, offset):
    return (offset, min(offset + 1, len(text))) if offset is not None and 0 <= offset <= len(text) else None


def frontend(source, expected_sha256):
    if source.identity != expected_sha256:
        raise report(source, "source", "source digest mismatch")
    if source.profile not in PROFILES:
        raise report(source, "profile", "unsupported requested profile version")
    try:
        text = source.data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise report(source, "source", "ill-formed UTF-8 source") from error
    try:
        term = parse(source.profile, text)
    except FrontendError as error:
        path = error.path if isinstance(error, HybridError) else ()
        span = point(text, error.offset)
        precision = "point"
        if path:
            span = json_locations(text).get(path)
            precision = "field"
            if span is not None and error.inner_offset is not None:
                mapped = scalar_point(text, span, error.inner_offset)
                if mapped is not None:
                    span, precision = mapped, "point"
        phase = "profile" if path == ("profile",) else "frontend"
        raise report(source, phase, str(error), text, span, path, precision) from error
    return normalize(source, term)


def normalize(source, term):
    try:
        return FrontendOutput(source, canonical(term))
    except FrontendError as error:
        raise report(source, "normalization", str(error)) from error


def generate(parsed, target_profile):
    if target_profile not in PROFILES:
        raise report(parsed.source, "generation", "unsupported target profile version")
    try:
        text = render(target_profile, json.loads(parsed.normalized))
        reparsed = canonical(parse(target_profile, text))
    except FrontendError as error:
        raise report(parsed.source, "generation", "term is outside target profile") from error
    if reparsed != parsed.normalized:
        raise report(parsed.source, "generation", "target profile changes normalized expression")
    return Generated(Source(target_profile, text.encode()), parsed.source.profile,
                     parsed.source.identity, parsed.normalized_digest)


def elaborate(parsed, program_factory):
    try:
        return compile_program(program_factory(json.loads(parsed.normalized)))
    except RepresentationError as error:
        raise report(parsed.source, "elaboration", str(error)) from error


def check_semantics(parsed, graph, oracle):
    try:
        validate_graph(graph)
    except RepresentationError as error:
        raise report(parsed.source, "semantic-validation", str(error)) from error
    if not oracle(graph):
        raise report(parsed.source, "semantic-validation", "independent observation mismatch")


def diagnostic_record(error):
    record = asdict(error.diagnostic)
    record["path"] = list(record["path"])
    return record
