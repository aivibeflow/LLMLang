# RT-10 — File and startup observations under glibc and musl

- **Date** — 2026-11-25
- **Tracking** — [PLAN §5.3](../../../PLAN.md#53-posix-architecture-and-conformance) · [#326](https://github.com/aivibeflow/LLMLang/issues/326)
- **Status** — Reproduced agreement for two libc implementations on the same Linux profile

## Question and method

Which observed file and process-start behaviors survive a change of POSIX-facing libc? The fixture reuses the two exact C probes for descriptor identity and child startup. GCC builds each probe at O0 and O2 against glibc 2.41 and musl 1.2.5. The linker reports the exact selected `libc.a` path. The harness confirms each static artifact has neither an ELF interpreter nor a dynamic needed library and records the selected archive and artifact digests. Both implementations run on one Linux x86-64 kernel and overlay filesystem. [File identity probe](RT-10-POSIX-FILE-IDENTITY-2026-11-25.md) · [Spawn descriptor probe](RT-10-POSIX-SPAWN-DESCRIPTORS-2026-11-25.md)

```mermaid
flowchart LR
    P["Pinned POSIX C probes"] --> G["Static glibc builds"]
    P --> M["Static musl builds"]
    G --> A["Verify selected archive and ELF closure"]
    M --> A
    A --> R["Compare native observations with contract fixtures"]
```

## Results

| Check | glibc 2.41, O0 and O2 | musl 1.2.5, O0 and O2 |
|---|---:|---:|
| File identity fields per execution | 21 | 21 |
| Startup case outcomes per execution | 8 | 8 |
| Repetitions per optimization level and fixture | 4 | 4 |
| Checked file fields and startup outcomes | 232 | 232 |

All 464 checks match the original contract fixtures. Both libcs preserve shared offsets under duplication and independent offsets under separate opens. Both preserve live access through descriptors after names are removed. The startup cases agree on marked-slot closure across exec, explicit slot mapping and the different behavior of same-slot raw duplication and same-slot spawn actions. Both return `EBADF` directly for the two invalid spawn mapping sequences in this setup. [Exact evidence](POSIX-CROSS-LIBC-01/evidence.json)

This supplies a common bounded contract for these two Linux libc profiles. Static linkage and selected archive evidence rule out an accidental comparison of the same runtime provider. Additional kernels, filesystem profiles, ABI variants and scheduling conditions remain open, as do profile-specific error reports outside these startup cases.

## Reproduction

Use Linux x86-64, GCC 14.2.0 (Debian 14.2.0-19), GNU binutils 2.44, glibc 2.41 development files, and CPython 3.12.14. The Debian trixie development package provides the musl headers, archive and GCC specs. Its published SHA-256 is recorded below. The harness relocates the packaged GCC specs into the temporary build directory and checks the actual linker selection. [Debian package](https://deb.debian.org/debian/pool/main/m/musl/musl-dev_1.2.5-3.1~deb13u1_amd64.deb) · [Runner](POSIX-CROSS-LIBC-01/run.py)

```sh
set -eu
dir=research/runtime-and-systems/RT-10/POSIX-CROSS-LIBC-01
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
package=musl-dev_1.2.5-3.1~deb13u1_amd64.deb
curl -fsSL "https://deb.debian.org/debian/pool/main/m/musl/$package" -o "$scratch/$package"
printf '%s  %s\n' a3f7d47e452129bb65aae201d6c115abf4d5d3efb136b38b7c6b4fa03ec065e9 "$scratch/$package" | sha256sum -c
dpkg-deb -x "$scratch/$package" "$scratch/musl"
python3 -B "$dir/run.py" --musl-root "$scratch/musl" > "$scratch/evidence.json"
cmp "$dir/evidence.json" "$scratch/evidence.json"
```
