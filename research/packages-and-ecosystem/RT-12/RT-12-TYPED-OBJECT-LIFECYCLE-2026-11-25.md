# RT-12 strict typed object admission and immutable storage versions

**Date** 2026-11-25 · **Plan** §4.1 · **Issue** [#319](https://github.com/aivibeflow/LLMLang/issues/319)

The filesystem CAS combines the existing strict Python and JavaScript wire checks with the no-replace insertion primitive. It admits only canonical typed data in the requested domain. A signed or expected address is a transport input in a production implementation. This fixture supplies an exact claimed digest and verifies the bytes independently before insertion. It checks the storage envelope and inner typed bytes again on read.

Two storage envelope versions encode the same inner bytes at different physical content addresses. The candidate v2 adds the exact inner byte length. The shared inner digest remains unchanged and both versions load using eligible readers. The SQLite catalog identifies each physical address and its version. Mutable references use an expected prior address, and historical addresses remain separately readable after a reference moves.

| Boundary | Checked result |
| --- | --- |
| Strict typed wire | Both runtimes agree on all 31 wire cases, and storage admits exactly the inputs accepted by the strict validator. Alternative canonical spellings, malformed encodings, duplicate keys, unsupported algorithms and wrong domains are refused as appropriate. |
| Immutable storage identity | Repeating exact insertion preserves the original address. Revising the envelope creates a different physical address while preserving the inner typed identity. Changing the inner term changes its identity. |
| Read and reference scope | A v1-only reader rejects v2. Cross-domain reads and a stale expected reference are refused. |
| Malformed storage envelope | Unsupported and Boolean versions, a non-string inner address and an incorrect stored byte length are refused. |
| Occupied corrupted address | An exact reader detects changed bytes. Ordinary retry refuses to overwrite the occupied path. The independently stored version still reads the same inner object. |

The checked candidate separates canonical typed object identity, storage envelope identity and mutable catalog selection. It complements the existing concurrent and interrupted no-replace insertion fixture. Production SPG envelopes and hash registry, receipt authority, repair authorization and power-loss durability remain open. The storage formats serve this fixture.

Reproduce with Python 3.12.14, SQLite 3.53.1 and Node from the repository root.

```bash
study=research/packages-and-ecosystem/RT-12/TYPED-OBJECT-LIFECYCLE-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two independent runs produced byte-identical results for 31 wire inputs and nine lifecycle refusals.
