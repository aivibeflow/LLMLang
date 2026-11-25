#!/usr/bin/env bash
set -euo pipefail

root=research/compiler-and-translation/RT-13
export LC_ALL=C PYTHONHASHSEED=1
test "$(python3 -c 'import platform; print(platform.python_version())')" = 3.12.14
lean --version | grep -F 'commit 611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9'

out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT

check_proof() {
    local directory=$1 module=$2
    lean -DwarningAsError=true "$root/$directory/$module.lean" > "$out/axioms.txt"
    diff -u "$root/$directory/axioms.txt" "$out/axioms.txt"
    printf 'Checked Lean assertions and axiom transcript for %s\n' "$directory"
}

check_proof GRAPH-OCCURRENCE-01 Graph
check_proof EXHAUSTIVE-EVIDENCE-01 Coverage
check_proof PASS-COMPOSITION-01 Chain

for directory in GRAPH-OCCURRENCE-01 EXHAUSTIVE-EVIDENCE-01 DIFFERENTIAL-SHRINK-01 PASS-COMPOSITION-01; do
    python3 -B "$root/$directory/run.py" > "$out/evidence.json"
    diff -u "$root/$directory/evidence.json" "$out/evidence.json"
    printf 'Reproduced exact evidence for %s\n' "$directory"
done
