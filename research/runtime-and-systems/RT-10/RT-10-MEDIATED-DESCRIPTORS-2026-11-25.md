# RT-10 mediated native descriptors and runtime authority

**Date** 2026-11-25 · **Plan** §5.2 · **Issue** [#325](https://github.com/aivibeflow/LLMLang/issues/325)

A local runtime broker holds file descriptors for temporary fixtures. Signed grants bind an actor, resource, operation, runtime profile and authority epoch. The broker verifies the grant and checks the current epoch, exact opened file identity and native read or write mode before performing the requested effect. Revocation and the mediated effect run under one local lock.

| Boundary | Checked result |
| --- | --- |
| Valid read and write grants | The broker reads the exact first file and changes only the intended second file. |
| Wrong actor, resource, operation or runtime profile | The grant is refused for that requested scope. An altered or invalid authenticator also fails. |
| Valid grant with insufficient native access mode | The requested operation remains ineligible. A direct native read-only write also returns `EBADF`. |
| Revocation before the worker's scheduled effect | The mediated use of the old grant fails. A freshly issued grant succeeds for the same exact file. |
| Earlier transferred raw descriptor | Its own kernel lifetime preserves the opened file after application-level revocation. |
| Descriptor number points at a replacement fixture file | Exact opened-object verification refuses the request. |

Fifteen controls reproduce the requested scope, operation outcomes and ordering. A dynamically enforced grant can keep raw descriptors private while a broker mediates each effect. Grant validity is a separate condition from native descriptor mode and identity. The fixture supplies the caller identity and uses ephemeral local keys that never enter the evidence. It covers cooperative threads and own temporary files. Production authentication, cross-process isolation, platform-native revocation, lifecycle delegation and race policy beyond the scope remain open.

Reproduce with CPython 3.12.14 on Linux.

```bash
study=research/runtime-and-systems/RT-10/MEDIATED-DESCRIPTORS-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two runs with distinct ephemeral keys reproduced the evidence.
