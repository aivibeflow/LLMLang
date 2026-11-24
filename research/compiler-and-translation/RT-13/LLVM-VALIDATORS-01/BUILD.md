# Build the LLVM validation comparison

These notes capture the toolchain paths used for this experiment. Start each build from the specified upstream source revision.

## LLVM and Alive2

Install Debian LLVM 19.1.7 with its CMake files and development headers, Z3 development files, a C++ compiler, CMake, Ninja, re2c and the development libraries required by the packaged LLVM configuration. The measured build used GCC 14 and the distribution's shared Z3.

The upstream Alive2 `v19.0` revision is `84041960f183aec74d740ff881c95a4ce5234d3d`. Stock CMake rejects LLVM configurations with exception handling disabled. The Debian build used here has RTTI enabled and exception handling disabled. Apply [the build-only patch](alive2-packaged-llvm-eh.patch) to an isolated checkout to repeat the experiment. It sets the consuming target's CMake exception-handling variable to on and retains a warning about the packaged LLVM. It does not rebuild that LLVM library.

```sh
git apply /absolute/path/to/alive2-packaged-llvm-eh.patch
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_LLVM_UTILS=ON -DLLVM_DIR=/usr/lib/llvm-19/lib/cmake/llvm
cmake --build build --target alive-tv -j1
```

The stock build path needs LLVM built with both `LLVM_ENABLE_EH=ON` and `LLVM_ENABLE_RTTI=ON`. The matching LLVM upstream revision is `cd708029e0b2869e80abe31ddb175f7c35361f90`. Point the unmodified Alive2 checkout at the LLVM build's CMake directory for that comparison. [Alive2 source](https://github.com/AliveToolkit/alive2/tree/84041960f183aec74d740ff881c95a4ce5234d3d) · [LLVM source](https://github.com/llvm/llvm-project/tree/cd708029e0b2869e80abe31ddb175f7c35361f90)

## Vellvm

Use revision `7f0610c38d829b79bf6e867edf410c9e6f928f98` in the Linux amd64 image `rocq/rocq-prover@sha256:9a1e969649a3cc3c6f310d5be5a842e2187384560337c6c0807aba9f8565efba`. The compiler switch is OCaml 4.14.2 with flambda. The build resolved Rocq 9.1.1, Flocq 4.2.2, Equations 1.3.1+9.1 and Menhir 20260209. [Vellvm](https://github.com/vellvm/vellvm/tree/7f0610c38d829b79bf6e867edf410c9e6f928f98) · [Installed package observations](vellvm-opam-versions.txt)

When the upstream package archives are available, install the matching opam dependencies. Use `ppxlib.0.32.0` for `ppx_optcomp.v0.16.0` on this switch. The version 0.38.0 selected without the pin failed while compiling `ppx_optcomp`, because its `Pexp_function` representation has changed.

```sh
opam install --yes --jobs=1 ppxlib.0.32.0
opam install --yes --jobs=1 --deps-only .
opam exec -- make -C src -j1 extracted
(cd src && opam exec -- dune build --build-dir _build-byte --profile release -j1 ml/main.bc)
```

The interpreter used to collect evidence was the bytecode target. The command below tests one case. For the Python runner, use [the bytecode wrapper](vellvm-byte.sh) with `VELLVM_BYTECODE` set to the bytecode path and the switch environment active.

```sh
opam exec -- ocamlrun src/_build-byte/default/ml/main.bc -test-file /path/to/identity.ll
```

The measured bytecode SHA-256 is `74f92fd9196514171d2cef05373dd752b1a41920687bab4206d4b097ab134237`. The experimental Alive2 executable SHA-256 is `fc7859bd3c985edc3694b262fc39813f57761cd5512f82685b7182b946774960`.

This run used source mirrors where the opam archive endpoints were unavailable. The local opam entries retained the upstream package versions and build instructions, replacing the download URLs and checksums. The Vellvm source was unmodified. The Menhir Debian repack drops manuals and images. Its parser package was built after removing the resulting unsatisfied `(include dune.manual)` directive from `doc/dune`. This changes the documentation build. The other Menhir packages used the same Debian repack without that edit.

| Download | Revision or SHA-256 |
| --- | --- |
| [Flocq Debian source archive](https://deb.debian.org/debian/pool/main/f/flocq/flocq_4.2.2.orig.tar.bz2) | `176914d121c09ee07679afd302fc42675592c4c3db2c1e3a71ad69b03c2b0a89` |
| [Menhir Debian source archive](https://deb.debian.org/debian/pool/main/m/menhir/menhir_20260209+ds.orig.tar.xz) | `f7f8535e1b95c693be8805bc6eaa624a3f4d0c1bbdfcdf5d76ae1e00e5147a80` |
| [Jane Street ppx_optcomp](https://github.com/janestreet/ppx_optcomp/tree/e70df92bf649771b7197a6efb1a9d1ee8f498c13) | Tag `v0.16.0`, commit `e70df92bf649771b7197a6efb1a9d1ee8f498c13` |
| [Jane Street stdio](https://github.com/janestreet/stdio/tree/3b3ea13acdce9d745724744ee9b7c52a2ba4add5) | Tag `v0.16.0`, commit `3b3ea13acdce9d745724744ee9b7c52a2ba4add5` |
| [Jane Street sexplib0](https://github.com/janestreet/sexplib0/tree/df916dfe8d0538a0dbfcdcb35c6e933ac9fc8130) | Tag `v0.16.0`, commit `df916dfe8d0538a0dbfcdcb35c6e933ac9fc8130` |

Use the linked versions to rebuild and compare the recorded case outputs. This provides tool source versions and the observed resolved dependency set. Package manager and tool compiler outputs can vary with the operating-system package snapshot.
