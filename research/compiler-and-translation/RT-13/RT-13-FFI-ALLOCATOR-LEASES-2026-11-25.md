# RT-13 Foreign allocator pairing and buffer leases

One C ABI can expose memory backed by different allocators. The release operation needs the provider instance, allocator kind and allocation generation that established ownership. A borrowed pointer also needs an exact borrow lifetime. Cancellation can request settlement without ending the borrow or making the allocation releasable.

```mermaid
flowchart LR
  A[Reserve under provider and allocator] --> B[Admit bounded exclusive borrow]
  B --> C[Request cancellation or complete]
  C --> S[Settle exact borrow ordinal]
  S --> R[Release through owning provider]
```

The native fixture links a client against a shared C provider on Linux. It compares heap `malloc/free` and anonymous `mmap/munmap` under two GCC optimization modes. Two distinct provider owners intentionally mint the same allocation generation. The wrong provider refuses before touching its allocator. A subtraction-based range check refuses an overflowing length. A second simultaneous borrow refuses, and cancellation keeps release busy until settlement. A replay of the first borrow's settlement cannot end its successor. After release and reallocation, the old allocation generation refuses, and the new bytes are zero.

Both builds match 48 independent expected observations in total. The raw heap request outside the allocation domain reports glibc `ENOMEM`. The zero-length mapping control reports kernel `EINVAL`. Those system errors stay separate from the adapter's typed range, owner, stale and busy dispositions. The native fixture captures the error immediately on the failure path.

The model uses one exclusive borrow per provider and serialized calls from a cooperating client. Borrowed pointers remain subject to the foreign caller's use contract. The integrated design should carry an exact provider and allocator binding, explicit byte range and borrow disposition through return, cancellation and close. Foreign-thread settlement and context-specific errors have separate evidence. [Native owned ABI](RT-13-NATIVE-OWNED-ABI-2026-11-24.md) · [Foreign-thread callback lifetime](RT-13-FFI-CALLBACK-LIFETIME-2026-11-25.md) · [Win32 failure capture](RT-13-FFI-WIN32-HEADER-IMPORT-2026-11-25.md) · [POSIX libc error carriers](../../runtime-and-systems/RT-10/RT-10-LIBC-ERROR-CARRIERS-2026-11-25.md)

Use GCC 14.2.0, glibc 2.41, GNU readelf 2.44 and CPython 3.12.14. Two hash seeds reproduce the [native evidence](FFI-ALLOCATOR-LEASE-01/evidence.json).

```sh
LC_ALL=C PYTHONHASHSEED=37 python -B research/compiler-and-translation/RT-13/FFI-ALLOCATOR-LEASE-01/check.py
```
