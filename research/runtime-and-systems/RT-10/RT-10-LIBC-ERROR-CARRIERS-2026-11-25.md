# RT-10 — Error carriers at a native C library boundary

What should an FFI wrapper record before another native call can change its error evidence? This study compares a return-carried pthread error with `read` and `open` failures that use thread-local `errno`. The branch baseline is `5758c6228271834c400d0e5c18795a270a61ee6b`. [Linux errno contract](https://man7.org/linux/man-pages/man3/errno.3.html) · [POSIX conformance issue](https://github.com/aivibeflow/LLMLang/issues/326)

| Native call | Return | Immediate error storage | Control |
|---|---:|---|---|
| First mutex try-lock | 0 | Prior `EINTR` | Succeeds despite the old error value |
| Second try-lock on held mutex | `EBUSY` | Prior `EINTR` | The error is the return value |
| Read one queued byte | 1 | Prior `ENOSPC` | Successfully returns the byte |
| Read invalid descriptor | −1 | `EBADF` | A later failing open changes that thread's value to `ENOENT` |

Two worker threads deliberately produce different errors and meet at a barrier before observing their own `errno`. The invalid read thread still records `EBADF` while the missing file thread records `ENOENT`. All six observations agree in four static builds across glibc and musl at optimization levels 0 and 2. The selected archive bytes are distinct. [Native observations](LIBC-ERROR-CARRIERS-01/evidence.json)

A caller-facing result should be built according to the selected function's return contract. A direct status remains part of its return value. An `errno`-based wrapper captures the error upon the function's documented failure return, in that thread and before another library call. A successful return can coexist with a prior `errno`. The experiment covers these native APIs on Linux with controlled threads and an absent file path in the temporary fixture. Ambiguous sentinel APIs, asynchronous callbacks, foreign exception mechanisms and other runtime profiles remain open. [POSIX runtime architecture](POSIX-RUNTIME-ARCHITECTURE.md)

## Reproduction

Use x86-64 Linux 6.18.57, GCC 14.2.0 (Debian 14.2.0-19), glibc 2.41, musl 1.2.5, GNU Binutils 2.44 and CPython 3.12.14. Acquire and verify the musl archive with the [cross-libc setup](RT-10-POSIX-CROSS-LIBC-2026-11-25.md#reproduction). Hash seeds 1 and 2 produced identical receipts.

```bash
fixture=research/runtime-and-systems/RT-10/LIBC-ERROR-CARRIERS-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" --musl-root /path/to/extracted/musl > /tmp/llmlang-rt10-libc-errors.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt10-libc-errors.json
```
