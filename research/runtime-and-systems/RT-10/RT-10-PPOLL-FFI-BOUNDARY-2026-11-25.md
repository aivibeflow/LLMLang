# RT-10 libc and Linux ppoll ABI boundaries

**Date** 2026-11-25 · **Plan** §5.3 · **Issue** [#326](https://github.com/aivibeflow/LLMLang/issues/326)

The fixture compares the portable libc call shape for `ppoll` with the Linux x86-64 syscall adapter. The candidate API represents the ordinary timeout as input and the resulting readiness in the returned carrier. The native syscall also accepts a mutable remaining-time pointer and requires the exact kernel signal mask size. Independently linked glibc and musl builds verify the selected archive.

| Observation | Libc call | Linux x86-64 syscall |
| --- | --- | --- |
| Timeout expires on an empty pipe | Zero readiness, original timeout retained | Zero readiness, remaining timeout becomes zero |
| Pipe has one byte | `POLLIN` and exact byte delivery | `POLLIN` and exact byte delivery |
| Negative timeout | `EINVAL` | `EINVAL` |
| Signal mask storage | Native libc `sigset_t` is 128 bytes in these profiles | Kernel adapter supplies an eight-byte mask. Sending the libc size is refused with `EINVAL`. |
| Temporary mask on return | Original thread mask restored | Original thread mask restored |

All 140 native observations agree with the declared oracle at two optimization levels. The expired successful result retains a stale `errno` in both paths. A portable wrapper can expose readiness and timeout disposition, while a target-specific syscall adapter owns translation of pointer direction, mask representation, and the native error channel. The tested program uses an empty temporary signal mask and one Linux architecture. Other mask conversions, kernels, architectures, standard edition claims and broader ABI correspondence remain open.

Reproduce with GCC 14.2.0 and CPython 3.12.14 using the pinned musl development sysroot from the [cross-libc fixture](RT-10-POSIX-CROSS-LIBC-2026-11-25.md).

```bash
study=research/runtime-and-systems/RT-10/PPOLL-FFI-BOUNDARY-01
python "$study/run.py" --musl-root "$MUSL_SYSROOT" | cmp "$study/evidence.json" -
```

Two independent builds reproduced all scoped observations byte for byte.
