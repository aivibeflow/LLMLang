# Package Identity Prototype 01

**Status:** exploratory executable model; not normative LLMLang code.

## Run

Requires Python 3.11+ (uses the standard-library `tomllib` parser):

```sh
python -m unittest -v
python -m py_compile package_identity.py test_package_identity.py
```

The tests exercise PMI-001–PMI-014 from the parent design note, plus typed-encoding, duplicate-TOML-key, root-membership, cache-index shape/uniqueness/collision, and canonical-path checks. Run discovery from this directory so both test modules are included: `python -m unittest discover -v`. The prototype uses SHA-256 with domain separation and an explicit typed encoding solely to make the candidate model executable. Neither choice is accepted as the final LLMLang wire/hash specification.

## Scope and limitations

- The index fixture is a small in-memory logical table model, not the proposed binary `index.bin` format.
- The prototype canonicalizes records as unordered sets. Final table schemas must specify keys, uniqueness, and which collections are ordered.
- PMI-012 demonstrates invalidation when a dependency target changes under a stale declared index hash; it does not yet implement provider-side transitive dependency resolution or missing-object closure checks. The manifest model now also rejects roots absent from the included-object table, but this is not a substitute for validating the full dependency closure.
- PMI-014 demonstrates equivalent logical inputs; it does not invoke separate static and dynamic package builders.
- PMI-008 tests the logical/physical boundary at the model interface; no real index encoder, compression codec, block directory, or sparse index exists yet.
- PMI-010 keeps provenance outside the hash API; it does not parse, authenticate, or verify provenance/signatures.
- PMI-010 tests the architectural boundary that provenance is not an identity input; provenance parsing/signature verification is outside this prototype.
- The TOML parser currently enforces a deliberately narrow candidate schema. It is not a production security-hardened archive extractor.
- This directory does not implement compression, sparse indexes, archive I/O, provider protocols, signatures, or trust policy. The sibling Package Index Prototype 01 has an exploratory ZIP writer/verifier that reuses this module's manifest parser and root-hash projection; it recomputes the index hash from streamed table files rather than materializing the logical index. The ZIP layout and canonical encoding remain non-normative.

The prototype is intended to expose ambiguities and produce executable fixtures before a normative format is drafted.

## Composite language version and cache-index prototype

The experimental `language_version.py` and `cache_index.py` modules validate the append-only component registry, composite version coordinates, and candidate cache records. Run them with the normal package prototype test discovery command. The cache record schema and Action Key construction are exploratory and are not normative.
