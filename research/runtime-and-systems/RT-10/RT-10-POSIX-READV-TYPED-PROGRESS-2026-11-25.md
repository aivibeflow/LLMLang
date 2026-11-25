# RT-10 — Typed progress for POSIX vector reads

What information should a typed facade preserve when a vector read returns zero, reports would-block, or fills only part of its destination? The fixture compares Linux `readv` with four result variants and two retry strategies. The branch baseline is `1c736c5fce66ef36735607a7e9201d8581ee966b`. [One-call pipe I/O facade](RT-10-POSIX-NONBLOCKING-PIPE-IO.md) · [Linux readv contract](https://man7.org/linux/man-pages/man2/readv.2.html)

The runner uses fresh nonblocking pipes, six destination shapes, payload lengths zero through eight, and open or closed writers. It checks each filled buffer and reads the remaining pipe data to verify the amount actually consumed. The one-call facade distinguishes zero total requested length, would-block, end of file and positive progress.

| Typed disposition | Native observation | Cases |
|---|---|---:|
| Zero request | Count 0 with a zero total destination length | 36 |
| Would-block | `EAGAIN` with a positive request, an empty pipe and a live writer | 4 |
| EOF | Count 0 with a positive request and no remaining data from the closed writer | 4 |
| Progress | Positive count with exact writes across the vector | 64 |

Zero-length requests consume nothing even in the presence of queued bytes. A zero return therefore identifies EOF only after the facade has established a nonzero request in this profile. In the progress cases, the aggregate count and known vector lengths identify exactly which prefix of the destination was initialized. [All 108 observations](POSIX-READV-PROGRESS-01/evidence.json)

A second comparison uses destination lengths 2, 3 and 2. The first read consumes `abc`, producing `ab`, `c__`, and `__` with underscore sentinels. The next read consumes `defg`. Resuming at the recorded offset produces `ab`, `cde`, and `fg`. Reissuing the full vector produces `de`, `fg_`, and `__`, overwriting the progress from the first call. Both variants drain the pipe, so successful syscall counts do not establish preservation of the whole logical response.

The facade can report a progress count with an exact destination prefix and build the next vector from the remaining elements. The study covers Linux nonblocking pipe inputs with one reader and one controlled writer, including empty vector entries. Concurrent descriptor lifetimes, signals, cancellation, socket variants, multi-libc comparison and general POSIX conformance remain open. [POSIX conformance issue](https://github.com/aivibeflow/LLMLang/issues/326)

## Reproduction

CPython 3.12.14 uses `os.readv` on Linux 6.18.57. Hash seeds 1 and 2 produced identical receipts.

```bash
fixture=research/runtime-and-systems/RT-10/POSIX-READV-PROGRESS-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > /tmp/llmlang-rt10-readv-progress.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt10-readv-progress.json
```
