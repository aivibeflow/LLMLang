#!/usr/bin/env bash
set -euo pipefail
source_dir=$(cd -- "$(dirname -- "$0")" && pwd)
provider=$(realpath -- "${1:?path to libmimalloc.so.2}")
output=${2:?path to sample CSV}
temp_dir=$(mktemp -d)
trap 'rm -rf "$temp_dir"' EXIT
for opt in 0 3; do
    rustc --edition 2021 --crate-type cdylib --crate-name buffer_provider \
        -C "opt-level=$opt" -C panic=abort "$source_dir/provider.rs" \
        -o "$temp_dir/libbuffer_provider.so"
    gcc -std=c11 -Wall -Wextra -Werror "-O$opt" "$source_dir/client.c" \
        -L"$temp_dir" -lbuffer_provider -Wl,-rpath,\$ORIGIN -ldl -o "$temp_dir/client"
    env -u LD_PRELOAD "$temp_dir/client" "$provider" > "$temp_dir/results-$opt.csv"
done
cmp "$temp_dir/results-0.csv" "$temp_dir/results-3.csv"
cp "$temp_dir/results-3.csv" "$output"
