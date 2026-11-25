# RT-12 portable manifest scalar profile

A strict Python manifest gate and the independent Go reader agree on all 41 cases. Both accept 20 cases with identical canonical preimages, logical index hashes and package roots. Both refuse 21 cases. The Python gate closes four previous version-type differences and five integer-range differences in this corpus.

## Candidate rule

Manifest schema and index format versions must have TOML integer type and the declared value. Boolean and floating-point values retain their own types. Resolution inputs admit Boolean and string values, signed 64-bit TOML integers, arrays and string-keyed tables. The integer range applies recursively through arrays and tables. The typed hash continues to distinguish the admitted logical values. Standalone canonical integers have their own existing test profile and may have a different range. [Previous independent comparison](RT-12-INDEPENDENT-PACKAGE-IDENTITY-2026-11-25.md)

| Input family | Observed result |
| --- | --- |
| Top-level and index version fields | Decimal, hexadecimal and explicitly signed integer spellings admit version 1. Boolean, floating-point and string substitutions are refused. |
| Signed 64-bit endpoints | Both endpoints are admitted. The decimal, formatted decimal and hexadecimal encodings of the maximum map to the same package root. |
| Out-of-range resolution inputs | Positive and negative overflow are refused, including high hexadecimal and nested array values. |
| Other archived manifest fields | Previous common acceptances retain their exact canonical bytes and hashes. Invalid closure membership, path, root and hash cases retain their previous refusal. |

The gate is an experimental wrapper around the existing Python identity prototype. The independent reader uses the same Go source and BurntSushi TOML v1.5.0 dependency as the earlier study. Go 1.24.13 built it with a temporary module directive at 1.24 because the Go 1.27.4 download was unavailable in this environment. The tracked Go files remain as specified by the original study. This evidence compares one portable candidate and SHA-256 domain separation for these cases. Formal schema acceptance, hash agility and the full streaming archive profile remain open.

## Reproduce

Use CPython 3.12.14 and Go 1.24.13 against the pinned module checksums. Seed 37 and seed 71 produced the same evidence SHA-256 `9729edcc0aa1ead2440e41d68c9d471e3539f0db9b13ac24e402b6879e3b7bac`. The ledger supplies canonical bytes, results, source hashes and the exact temporary module directive. [Evidence ledger](PORTABLE-MANIFEST-01/evidence.json)

```sh
set -eu
study=research/packages-and-ecosystem/RT-12
work=$(mktemp -d)
go_tool=/path/to/go1.24.13/bin/go
export GOPATH="$work/gopath" GOMODCACHE="$work/modules" GOCACHE="$work/build"
export GOENV=off GOTOOLCHAIN=local
cp "$study/INDEPENDENT-PACKAGE-IDENTITY-01/go.mod" "$study/INDEPENDENT-PACKAGE-IDENTITY-01/go.sum" "$work/"
(cd "$work" && "$go_tool" mod edit -go=1.24 && "$go_tool" mod download -modcacherw)
LC_ALL=C PYTHONHASHSEED=37 PYTHONDONTWRITEBYTECODE=1 \
  python "$study/PORTABLE-MANIFEST-01/check.py" --go "$go_tool" > "$work/evidence.json"
cmp "$work/evidence.json" "$study/PORTABLE-MANIFEST-01/evidence.json"
```
