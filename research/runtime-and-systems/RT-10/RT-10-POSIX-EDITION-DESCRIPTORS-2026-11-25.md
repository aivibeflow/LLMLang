# RT-10 — POSIX edition claims and descriptor feature coverage

Does selecting an edition feature-test macro establish the descriptor operations an LLMLang runtime can use? This experiment compares the older and newer POSIX feature-test requests and an explicit GNU request under glibc and musl. The branch baseline is `74636c8aa48e43495925d3a0f36682721dee1ad9`. [Issue 7 pipe contract](https://pubs.opengroup.org/onlinepubs/9699919799/functions/pipe.html) · [Issue 8 descriptor flag resolution](https://www.austingroupbugs.net/view.php?id=1577)

The baseline uses `pipe` and `fcntl`. The edition-specific checks use `pipe2`, `dup3`, and the close-on-fork flags `O_CLOFORK` and `FD_CLOFORK`. The source probes independently test header visibility and run each accepted case with a verified, statically linked libc archive. The `pipe2` check requires nonblocking and close-on-exec flags on both ends. The `dup3` check requires the destination flag and verifies that passing the same descriptor twice yields `EINVAL`. [Linux pipe and edition history](https://man7.org/linux/man-pages/man2/pipe.2.html) · [Linux duplication contract](https://man7.org/linux/man-pages/man2/dup.2.html)

| Static libc profile | Feature-test request | Baseline | `pipe2` and `dup3` | Close-on-fork flags |
|---|---|---|---|---|
| glibc 2.41 | `200809L` | Pass | Declarations unavailable | Unavailable |
| glibc 2.41 | `202405L` | Pass | Declarations unavailable | Unavailable |
| glibc 2.41 | `_GNU_SOURCE` | Pass | Both pass native checks | Unavailable |
| musl 1.2.5 | `200809L` | Pass | Both pass native checks | Unavailable |
| musl 1.2.5 | `202405L` | Pass | Both pass native checks | Unavailable |
| musl 1.2.5 | `_GNU_SOURCE` | Pass | Both pass native checks | Unavailable |

All six baseline runs report 200809 in both the header version and `sysconf(_SC_VERSION)`. Both libc profiles ran on one fixed Linux kernel and used distinct archive bytes. The 24 compiler cases yield 14 native runs. Glibc exposes the tested functions under its GNU feature request, while musl exposes them under both POSIX requests as well. Both headers lack the two close-on-fork flags under all three requests. The fixture therefore records no native close-on-fork test for these builds. [Exact header and runtime receipts](POSIX-EDITION-DESCRIPTORS-01/evidence.json) · [Linux open flag support](https://man7.org/linux/man-pages/man2/open.2.html)

The tested descriptor slice has a common baseline and two individually available atomic-flag operations. The observations support a per-operation feature matrix with separate rows for edition requirements, header visibility, and checked behavior. Full Issue 8 coverage and any normative initial edition selection remain open. Other kernels, dynamic linkage and real concurrent fork/exec behavior were outside this fixture. [POSIX conformance issue](https://github.com/aivibeflow/LLMLang/issues/326)

## Reproduction

Use x86-64 Linux 6.18.57, GCC 14.2.0 (Debian 14.2.0-19), glibc 2.41 development files, GNU Binutils 2.44 and CPython 3.12.14. Obtain and verify the Debian musl 1.2.5 development archive using the [cross-libc reproduction instructions](RT-10-POSIX-CROSS-LIBC-2026-11-25.md#reproduction). This runner reuses the selected archive and ELF checks from that study. Hash seeds 1 and 2 yielded identical receipts.

```bash
fixture=research/runtime-and-systems/RT-10/POSIX-EDITION-DESCRIPTORS-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" --musl-root /path/to/extracted/musl > /tmp/llmlang-rt10-posix-edition.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt10-posix-edition.json
```
