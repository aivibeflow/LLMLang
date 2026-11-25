#!/bin/sh
# Run from the pinned RISCV64 l4v workbench after the official Refine check.
set -eu

study=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
rt38=$(dirname "$study")
test "$(git rev-parse HEAD)" = 12c300e75bb0ca0c82f76496fafacd7e614c0aba
test "$(git -C ../seL4 rev-parse HEAD)" = 62e345c240a15671484530b4e6e069ce266c28d7
export L4V_ARCH=RISCV64
unset L4V_FEATURES L4V_PLAT SKIP_AINVS_PROOFS AINVS_QUICK_AND_DIRTY SKIP_REFINE_PROOFS REFINE_QUICK_AND_DIRTY
isabelle=./isabelle/bin/isabelle
test "$("$isabelle" version)" = Isabelle2025-2
test "$("$isabelle" options -b -g skip_proofs)" = false
test "$("$isabelle" options -b -g quick_and_dirty)" = false

temporary=$(mktemp -d "${TMPDIR:-/tmp}/llmlang-lookup-source.XXXXXX")
trap 'rm -rf "$temporary"' EXIT HUP INT TERM
mkdir "$temporary/abstract" "$temporary/design" "$temporary/source"
cp "$rt38/SEL4-ABSTRACT-LOOKUP-01/ROOT" "$rt38/SEL4-ABSTRACT-LOOKUP-01/AbstractLookup.thy" "$temporary/abstract"
cp "$rt38/SEL4-LOOKUP-01/ROOT" "$temporary/design"
cp "$study/ROOT" "$temporary/source"
python3 "$rt38/SEL4-LOOKUP-01/export_lookup.py" "$rt38/SEL4-LOOKUP-01/lookup.json" \
  "$rt38/SEL4-LOOKUP-01/Lookup.thy.in" "$temporary/design/Lookup.thy"
printf '9e9d981f3420929756f6af2c74cd9b9a640e947ccaa74f871752c882ca42d48f  %s\n' \
  "$temporary/design/Lookup.thy" | sha256sum -c
python3 "$study/export_bytes.py" --output "$temporary/source/SourceLookup.thy"
sha256sum "$temporary/source/SourceLookup.thy"
"$isabelle" build -c -v -o threads=1 -o timeout_scale=4 -j1 -d . \
  -d "$temporary/abstract" -d "$temporary/design" -d "$rt38/SEL4-REFINED-LOOKUP-01" \
  -d "$temporary/source" LLMLang_LookupSource
