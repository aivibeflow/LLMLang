# RT-10 — Isolate Linux syscall ABIs across x86-64 and AArch64

Can one I/O contract stay unchanged when the Linux machine-level syscall entry changes? The fixture links identical freestanding C code against separate architecture assembly files. The branch baseline is `801d74b01a83ac4ee83f3af6d050fadb8f3bd8ba`. [Linux syscall ABI](https://man7.org/linux/man-pages/man2/syscall.2.html) · [POSIX conformance issue](https://github.com/aivibeflow/LLMLang/issues/326)

| Linux ABI | Entry instruction | Number register | Read, write, exit numbers | Observation mode |
|---|---|---|---|---|
| x86-64 | `syscall` | `rax` | 0, 1, 60 | Native |
| AArch64 | `svc #0` | `x8` | 63, 64, 93 | QEMU Linux user mode |

The assembly layers provide a process entry, read, write, and exit. The same C layer checks `EBADF` on a deliberately invalid descriptor, distinguishes a zero-length request from a positive read that reaches EOF, checks untouched buffer suffixes, and reports exact byte progress. The descriptor arguments follow the target C call convention and match the first three syscall parameter registers on each tested architecture. The code uses no libc. The runner checks ELF machine type, interpreter absence and absence of shared-library dependencies. [x86-64 adapter](LINUX-SYSCALL-ARCHITECTURES-01/x86_64.S) · [AArch64 adapter](LINUX-SYSCALL-ARCHITECTURES-01/aarch64.S)

The two builds per architecture agree with the independent expected traces on all six inputs, for 24 cases. A five-byte payload yields four bytes, one byte and EOF. A payload containing zero and two non-ASCII bytes is preserved exactly. The raw invalid call and zero-length call both leave the destination bytes unchanged. [Exact ELF identities and traces](LINUX-SYSCALL-ARCHITECTURES-01/evidence.json)

The evidence supports keeping target syscall numbers, entry registers, and termination in architecture-specific adapters under one checked C contract. x86-64 has native execution evidence. AArch64 has cross-link and Linux user emulation evidence using the host kernel. Physical AArch64 execution, signal and thread behavior, broader syscall coverage, native timing and any normative initial architecture selection remain open. [Linux runtime architecture](POSIX-RUNTIME-ARCHITECTURE.md)

## Reproduction

Use CPython 3.12.14, x86-64 Linux 6.18.57, GNU Binutils 2.44, Clang and LLD 23.1.1 from LLVM revision `6dfe1677ab8dffbc6ec13d53a1e0215d75147689`, and QEMU user mode 10.0.13. The Debian QEMU package SHA-256 is `ca6ede739327a20ae5a3498230c8a3a9a072c586e131bc6bcc1201eb1725e336`. The runner records the selected emulator executable hash. Hash seeds 1 and 2 produced identical receipts. [Pinned Debian package](https://deb.debian.org/debian/pool/main/q/qemu/qemu-user_10.0.13+ds-0+deb13u1_amd64.deb)

```bash
fixture=research/runtime-and-systems/RT-10/LINUX-SYSCALL-ARCHITECTURES-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" --clang /path/to/pinned/clang --qemu /path/to/qemu-aarch64 > /tmp/llmlang-rt10-syscall-arch.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt10-syscall-arch.json
```
