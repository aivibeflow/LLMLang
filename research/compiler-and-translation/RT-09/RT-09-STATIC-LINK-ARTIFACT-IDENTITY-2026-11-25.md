# RT-09 — Archive order, selected members and linked artifact identity

Which archive changes can affect a generated executable, and which identity should an exact build or preservation record retain? This fixture links the same caller against deterministic static archives with known member contents and order. The branch baseline is `0ce1b1dbd4eb842d850dd823184f5a066157d813`. [Cross-toolchain cache evidence](../../toolchain-and-collaboration/RT-11/RT-11-CROSS-TOOLCHAIN-CACHE-COMPATIBILITY-2026-11-25.md) · [Translation architecture issue](https://github.com/aivibeflow/LLMLang/issues/327)

Two archive members offer the same C symbol and return the input plus 1 or plus 2. A third member provides a separate marker symbol. The runner creates each archive using GNU `ar` deterministic mode, records its ordered members and reads the actual selected members from the GNU link map. It retains the exact linked ELF digest and outputs for inputs 0 through 15. Each case is built in two independent physical directories.

| Change relative to alpha first | Archive bytes | Selected members | ELF identity | Public behavior |
|---|---|---|---|---|
| Put beta first with the same member byte set | Different | Beta | Different | All 16 outputs differ |
| Change the unused marker member | Different | Alpha | Same | All 16 outputs agree |
| Omit the unused members | Different | Alpha | Same | All 16 outputs agree |
| Retain the same archive and force the marker symbol | Same | Alpha and marker | Different | All 16 outputs agree |

Both fresh roots reproduce the same observations and digests. The default static archive search selects the first available provider in this fixture. An unordered member set loses this distinction. Conversely, changing the archive around the selected provider can leave the linked bytes exactly equal. The forced-symbol control shows how changing the link request can change artifact identity even with the same archive and ordinary behavior. [Exact archive, link map and behavior receipts](STATIC-LINK-ARTIFACT-IDENTITY-01/evidence.json)

The results support tracking the ordered build input and link flags, the realized member selection, the exact output artifact and the observed behavior as related records. Each answers a different reproducibility question. The fixture covers one ordinary GNU static archive and one native link profile. Thin archives, multi-archive grouping, LTO, other linkers, release provenance and proof reuse remain open. [Selected runtime provider evidence](../RT-13/RT-13-WIDE-DIVISION-CAPABILITY-2026-11-25.md)

## Reproduction

Use GCC 14.2.0 (Debian 14.2.0-19), GNU Binutils 2.44 and CPython 3.12.14 on x86-64 Linux. Hash seeds 1 and 2 produced identical receipts.

```bash
fixture=research/compiler-and-translation/RT-09/STATIC-LINK-ARTIFACT-IDENTITY-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > /tmp/llmlang-rt09-link-artifact.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt09-link-artifact.json
```
