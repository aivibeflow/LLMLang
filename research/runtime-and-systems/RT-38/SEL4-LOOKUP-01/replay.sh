#!/bin/sh
# Run from the pinned l4v checkout with the study directory as argument.
set -eu

study=$(cd "$1" && pwd)
test "$(git rev-parse HEAD)" = 12c300e75bb0ca0c82f76496fafacd7e614c0aba
test "$(git -C ../seL4 rev-parse HEAD)" = 62e345c240a15671484530b4e6e069ce266c28d7
export L4V_ARCH=RISCV64
unset L4V_FEATURES L4V_PLAT
isabelle=./isabelle/bin/isabelle
test "$("$isabelle" options -b -g skip_proofs)" = false

./run_tests -j1 -f -v --junit-report "$study/replay-reference.xml" ASpec ExecSpec
printf '%s\n' \
  'c7546bb714c8b814fff14270354c9c370906c7b0e14526ec20f4e6218ec56962  spec/design/CSpace_H.thy' \
  '42b1e10e11eac98dba74cb7611159432a18a06f826733a62e8714d1887c7e0c1  spec/machine/RISCV64/Kernel_Config.thy' \
  | sha256sum -c

python3 "$study/export_lookup.py" "$study/lookup.json" "$study/Lookup.thy.in" "$study/Lookup.thy"
printf '%s  %s\n' '9e9d981f3420929756f6af2c74cd9b9a640e947ccaa74f871752c882ca42d48f' \
  "$study/Lookup.thy" | sha256sum -c
"$isabelle" build -d . -d "$study" -o threads=1 -j1 -v LLMLang_Lookup
