#!/bin/sh
# Run from the pinned configured l4v checkout described by SEL4-LOOKUP-01.
set -eu

test "$#" -le 1
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
printf '%s\n' \
  'a4155cda63d033f8f6846ab73b0569c4718c779a4715d1311dad4b3177106b27  proof/refine/Ipc_R.thy' \
  'c7546bb714c8b814fff14270354c9c370906c7b0e14526ec20f4e6218ec56962  spec/design/CSpace_H.thy' \
  '1aad618124c55e0b304f10229b8c3686d4cd1536b64661e4565b594bb1818cc6  proof/invariant-abstract/Syscall_AI.thy' \
  | sha256sum -c

if [ "$#" -gt 0 ]; then
    export ISABELLE_BUILD_OPTS="-o threads=1 -o timeout_scale=4 -j1"
    ./run_tests -j1 -f -v --junit-report "$1" Refine
fi

temporary=$(mktemp -d "${TMPDIR:-/tmp}/llmlang-refined-lookup.XXXXXX")
trap 'rm -rf "$temporary"' EXIT HUP INT TERM
mkdir "$temporary/abstract" "$temporary/design"
cp "$rt38/SEL4-ABSTRACT-LOOKUP-01/ROOT" "$rt38/SEL4-ABSTRACT-LOOKUP-01/AbstractLookup.thy" "$temporary/abstract"
cp "$rt38/SEL4-LOOKUP-01/ROOT" "$temporary/design"
python3 "$rt38/SEL4-LOOKUP-01/export_lookup.py" "$rt38/SEL4-LOOKUP-01/lookup.json" \
  "$rt38/SEL4-LOOKUP-01/Lookup.thy.in" "$temporary/design/Lookup.thy"
printf '9e9d981f3420929756f6af2c74cd9b9a640e947ccaa74f871752c882ca42d48f  %s\n' "$temporary/design/Lookup.thy" | sha256sum -c
"$isabelle" build -c -v -o threads=1 -o timeout_scale=4 -j1 -d . \
  -d "$temporary/abstract" -d "$temporary/design" -d "$study" LLMLang_RefinedLookup
