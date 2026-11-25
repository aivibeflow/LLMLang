# RT-10 descriptor-relative POSIX operations and ambient cwd

**Date** 2026-11-25 · **Plan** §5.3 · **Issue** [#326](https://github.com/aivibeflow/LLMLang/issues/326)

A native program opens two directories with distinct file contents. Its worker changes the process working directory at an explicit thread barrier. A caller compares `AT_FDCWD`, its original directory descriptor and a duplicate of that descriptor. Another sequence renames the original directory and creates a replacement at the old pathname.

| Controlled schedule | Ambient or pathname lookup | Original and duplicated directory descriptors |
| --- | --- | --- |
| Original process cwd | A | A |
| Worker changes process cwd | B | A |
| Worker restores process cwd | A | A |
| Original path names a newly created directory | C | A |
| Original descriptor closes | Its old number fails with `EBADF` | Duplicate still reads A |

The retained descriptor has the same device and inode after rename. The recreated pathname refers to a different inode. Invalid directory, regular-file-as-directory and missing entry controls return `EBADF`, `ENOTDIR` and `ENOENT` respectively under the tested contract.

Seventy-two native result rows agree across independently linked static glibc and musl builds and two optimization levels. Each program uses real `fchdir`, barriers, `openat`, rename, close and file reads. The linker audit verifies the selected libc archives.

A portable bounded contract can admit descriptor-relative lookup independently of ambient cwd. Explicit environment-relative lookup observes the process cwd and namespace mutations. The exact descriptor lifetime and directory identity participate in the native adapter boundary. This fixture uses scoped names, one Linux filesystem and controlled threads. Cross-kernel conformance, policy for untrusted names or symlinks, open-file lifetime after removal and normative POSIX edition remain open.

Reproduce with GCC 14.2.0 and CPython 3.12.14 using the pinned musl development sysroot from the [cross-libc fixture](RT-10-POSIX-CROSS-LIBC-2026-11-25.md).

```bash
study=research/runtime-and-systems/RT-10/DIRECTORY-RELATIVE-POSIX-01
python "$study/run.py" --musl-root "$MUSL_SYSROOT" | cmp "$study/evidence.json" -
```

Two independent scheduled runs reproduced the ledger byte for byte.
