# RT-11 exact directional compatibility across language and tool identities

**Date** 2026-11-25 · **Plan** §3.3 · **Issue** [#300](https://github.com/aivibeflow/LLMLang/issues/300)

GCC builds C11 wrapping and saturating byte increments. Rust 1.85.1 builds their Rust 2021 counterparts. Each native entry returns the byte and writes a caller-visible provider marker. The fixture verifies that the four objects lack unresolved symbols and that the resulting shared objects have no ELF dynamic dependencies. An independent arithmetic oracle checks the result and marker for all 1,024 native calls.

Each profile binds exact source and object bytes, compiler parts, linker parts, observer, allowed native imports, build arguments, environment, target and closure digest. The compatibility receipt binds the two exact action keys, subject hashes and closure digests with direction, finite input scope, observation projection, checker and agreed observations. The experiment validates the declared context on a single fixed host. Its explicit dependency manifest is a fixture, and the native import checks are scoped to these objects and libraries.

| Projection and required inputs | Accepted directional comparisons out of 12 |
| --- | ---: |
| Return only, 0–254 | 12 |
| Return only, 0–255 | 4 |
| Return and provider marker, 0–254 | 4 |
| Return and provider marker, 0–255 | 0 |

The four full-domain matches compare C and Rust under the same arithmetic mode with the return-only projection. Input 255 distinguishes wrapping from saturation. The caller-visible marker distinguishes C from Rust under every input if the request includes that observation. Reusing the return receipt for an exact artifact request gives a miss. Each omitted receipt field is independently refused. A reversal of direction and two incomplete manifest controls are refused, including the case where the incomplete manifest is hashed again and assigned a new action key.

Require an exact complete dependency closure and exact Action Key for artifact reuse. Where a caller explicitly requests a portable scoped observation, a directional receipt can describe a compatibility result across distinct language and tool identities. It should identify the exact origin and destination actions and linked subjects, their verified closure, the covered input and observation scope, validation procedure and the common result digest. The scope has to cover the consuming request. This candidate provides finite equality evidence for one family of programs. A separately verified receipt can preserve that evidence. A general cross-version compatibility relation, production closure discovery, receipt authorization and host dependency isolation remain open.

Reproduce with GCC 14.2.0, Rust 1.85.1, GNU Binutils and CPython 3.12.14 on x86-64 Linux. For Rust the runner selects the actual compiler inside its sysroot.

```bash
study=research/toolchain-and-collaboration/RT-11/CROSS-LANGUAGE-RECEIPTS-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two builds in fresh directories reproduced the archived ledger byte for byte.
