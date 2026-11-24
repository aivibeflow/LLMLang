#!/bin/sh
# Run from the checked-out and configured l4v workbench used by SEL4-LOOKUP-01.
set -eu

study=$(cd "$1" && pwd)
test "$(git rev-parse HEAD)" = 12c300e75bb0ca0c82f76496fafacd7e614c0aba
test "$(git -C ../seL4 rev-parse HEAD)" = 62e345c240a15671484530b4e6e069ce266c28d7
export L4V_ARCH=RISCV64
unset L4V_FEATURES L4V_PLAT SKIP_AINVS_PROOFS AINVS_QUICK_AND_DIRTY

isabelle=./isabelle/bin/isabelle
test "$("$isabelle" options -b -g skip_proofs)" = false
test "$("$isabelle" options -b -g quick_and_dirty)" = false
printf '%s\n' \
  '1aad618124c55e0b304f10229b8c3686d4cd1536b64661e4565b594bb1818cc6  proof/invariant-abstract/Syscall_AI.thy' \
  '9f58f3582f852060606c6f55aff4f535076856ea5004a6c0900facc1397315e9  spec/abstract/CSpace_A.thy' \
  | sha256sum -c

if [ "${2:-}" = --rebuild-ainvs ]; then
  export ISABELLE_BUILD_OPTS="-o threads=1 -o timeout_scale=4 -j1"
  ./run_tests -j1 -f -v --junit-report "$study/ainvs-replay.xml" AInvs
fi

"$isabelle" build -c -v -o threads=1 -o timeout_scale=4 -j1 -d . -d "$study" LLMLang_AbstractLookup
