# Package Identity Prototype 01

**Status:** exploratory executable model; not normative LLMLang code.

## Run

Requires Python 3.11+ (uses the standard-library `tomllib` parser):

```sh
python -m unittest -v
python -m py_compile package_identity.py test_package_identity.py
```

The tests exercise PMI-001–PMI-014 from the parent design note, plus typed-encoding and duplicate-TOML-key checks. The prototype uses SHA-256 with domain separation and an explicit typed encoding solely to make the candidate model executable. Neither choice is accepted as the final LLMLang wire/hash specification.

## Scope and limitations

- The index fixture is a small in-memory logical table model, not the proposed binary `index.bin` format.
- The prototype canonicalizes records as unordered sets. Final table schemas must specify keys, uniqueness, and which collections are ordered.
- PMI-012 demonstrates invalidation when a dependency target changes under a stale declared index hash; it does not yet implement provider-side transitive dependency resolution or missing-object closure checks.
- PMI-014 demonstrates equivalent logical inputs; it does not invoke separate static and dynamic package builders.
- PMI-010 tests the architectural boundary that provenance is not an identity input; provenance parsing/signature verification is outside this prototype.
- The TOML parser currently enforces a deliberately narrow candidate schema. It is not a production security-hardened archive extractor.
- No compression, sparse index, archive, provider protocol, signatures, or trust policy is implemented.

The prototype is intended to expose ambiguities and produce executable fixtures before a normative format is drafted.
