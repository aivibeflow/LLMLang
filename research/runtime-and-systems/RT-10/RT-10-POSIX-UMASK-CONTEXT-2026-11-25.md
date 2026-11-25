# RT-10 — Process-wide umask and scoped file creation

Can a task temporarily change the creation mask without affecting a peer or a spawned process? The fixture compares an ambient mask override with an explicit mode on one creation call. The branch baseline is `a2bf637c30486184a2c6d4f6b073ac0f39dede0f`. [Linux umask contract](https://man7.org/linux/man-pages/man2/umask.2.html) · [POSIX conformance issue](https://github.com/aivibeflow/LLMLang/issues/326)

Each fixture begins at mask `0022`. A worker creates one new file. A peer creates a second file and spawns a new copy of the fixture executable, which creates a third. Two barriers establish whether those operations happen while the worker's mask override is active or after restoration. The per-call case requests mode `0600` for the worker and leaves the process mask at `0022`. Every case uses its own temporary directory without inherited fixture files.

| Schedule | Worker mode | Peer mode | Spawned process mode |
|---|---:|---:|---:|
| Baseline, all request `0666` | `0644` | `0644` | `0644` |
| Worker holds mask `0077` during peer operations | `0600` | `0600` | `0600` |
| Worker restores mask before peer operations | `0600` | `0644` | `0644` |
| Worker sets only its own requested mode | `0600` | `0644` | `0644` |

The two libc profiles and two optimization levels agree in 16 runs. The runner independently confirms the mode of each of the three files. The ambient overlap changes both the peer's operation and the mask inherited by the spawned process. Per-call restriction provides the selected worker mode and preserves the peer's expected mode in this scenario. [Exact modes and archive identities](POSIX-UMASK-CONTEXT-01/evidence.json)

This distinction informs how a facade describes effects on ambient process state. The tested requested mode can narrow permissions within the existing mask. More permissive modes, default ACLs, other filesystems, user and group inheritance, and controlled mutation of ambient state remain separate obligations. [POSIX runtime architecture](POSIX-RUNTIME-ARCHITECTURE.md)

## Reproduction

Use x86-64 Linux 6.18.57 with the fixture directory on overlayfs, GCC 14.2.0 (Debian 14.2.0-19), glibc 2.41, musl 1.2.5, GNU Binutils 2.44 and CPython 3.12.14. Acquire and verify the musl archive with the [cross-libc setup](RT-10-POSIX-CROSS-LIBC-2026-11-25.md#reproduction). Hash seeds 1 and 2 produced identical receipts.

```bash
fixture=research/runtime-and-systems/RT-10/POSIX-UMASK-CONTEXT-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" --musl-root /path/to/extracted/musl > /tmp/llmlang-rt10-posix-umask.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt10-posix-umask.json
```
