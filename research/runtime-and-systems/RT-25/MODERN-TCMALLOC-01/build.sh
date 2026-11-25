#!/bin/sh
# Build in an unpacked, disposable upstream source directory.
set -eu
if [ "$#" -ne 4 ]; then
    printf '%s\n' 'Usage: build.sh SOURCE BAZEL BAZEL_OUTPUT_ROOT JAVA_TRUSTSTORE' >&2
    exit 2
fi
study=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
source_dir=$(realpath "$1")
bazel=$(realpath "$2")
root=$(realpath -m "$3")
trust=$(realpath "$4")
cd "$source_dir"
mkdir -p llmlang_probe
cp "$study/BUILD.bazel" "$study/bridge.cc" llmlang_probe/
cp "$study/MODULE.bazel.lock" .
"$bazel" --batch --nosystem_rc --nohome_rc --noworkspace_rc --output_user_root="$root" \
    --host_jvm_args="-Djavax.net.ssl.trustStore=$trust" \
    build -c opt --jobs=2 --cxxopt=-std=c++17 --ignore_dev_dependency --lockfile_mode=error \
    --per_file_copt='^tcmalloc/.*\.cc$@-Wno-error=attributes,-Wno-error=class-memaccess' \
    //llmlang_probe:libllmlang_tcmalloc.so
