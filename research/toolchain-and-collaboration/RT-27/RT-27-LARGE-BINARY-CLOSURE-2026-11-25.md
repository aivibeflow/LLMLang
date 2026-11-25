# RT-27 portable Git reconstruction of large binary artifacts

**Date** 2026-11-25 · **Plan** §4.2 · **Issue** [#320](https://github.com/aivibeflow/LLMLang/issues/320)

Two GCC-built ELF applications each contain a deterministic non-allocated section. Each artifact is 3,170,080 bytes and emits a separately expected observation. Each semantic revision commits its exact root and a binary descriptor with whole-artifact digest, length, media type and delivery layout.

| Binary layout | Tracked files, including metadata | Recovery from a clean Git clone |
| --- | ---: | --- |
| Whole committed blob | 3 | Both revisions rebuild byte for byte with Git alone. |
| Four ordered 1 MiB content-addressed chunks, including a final partial chunk | 6 | Both revisions rebuild byte for byte with Git alone. Two exact chunks are shared between revisions. |
| Detached artifact by exact digest | 2 | Both revisions rebuild with the exact external bytes. A Git-only clone reports an unavailable artifact. |

All three Git histories pass full object validation. Fresh clones have no remote after fetching their histories and the sources are moved away. Every portable or externally completed restore replays the expected ELF stdout. The reader checks the pinned semantic root before checking any artifact. Missing, altered, shortened or reordered chunk data is refused by location, component size or final artifact identity. Reusing a valid binary from the other revision under the requested digest is also refused. Nine refusal controls cover the different layouts and exact historical scope.

When offline recovery requires an artifact, a closed Git carrier can include its exact whole bytes or a checked ordered chunk closure. A detached artifact locator expresses a dependency with its own availability requirement. The fixture uses portable local Git transfer and a supplied external byte map. It leaves production storage limits, platform ABI admission, cross-host builds, remote artifact lifetime and Git LFS host behavior open. The existing [native LFS study](../RT-24/RT-24-LFS-OBJECT-ADMISSION-2026-11-25.md) separately checks pointer and media identity.

Reproduce with GCC 14.2.0, GNU objcopy, Python 3.12.14 and Git 2.52.0 from the repository root.

```bash
study=research/toolchain-and-collaboration/RT-27/LARGE-BINARY-CLOSURE-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two fresh builds and repository sets produced byte-identical artifact identities and ledgers.
