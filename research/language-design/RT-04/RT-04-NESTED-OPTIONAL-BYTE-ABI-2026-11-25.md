# RT-04 — Native encodings of a nested optional byte

How can a fixed-width native boundary preserve the three branches of `Option<Option<Byte>>` and every payload? This study takes the distinct absence cases from [Scenario 62](RESEARCH-SCENARIO-62-OPTIONAL-VALUES-AND-NULLABILITY.md) and tests two candidate numeric layouts. The baseline on `research/all` is `4ecac0f9b0e21b2f77679bb7a66c1b272b2cf656`. [Sum type ABI alternatives](../../compiler-and-translation/RT-13/RESEARCH-SCENARIO-72-SUM-TYPE-LAYOUT-ABI-AND-INTEROPERABILITY.md)

The logical domain contains absent, present-empty, and present-byte for each of the 256 unsigned octet values. That gives 258 distinct values. Since 256 < 258 ≤ 512, any injective fixed-width bit encoding requires at least nine bits. Both candidate bridges expose a C `uint16_t` argument and result. The explicit-tag layout uses the upper octet for a tag and requires a zero lower octet for the first two states. The dense layout reserves codes 0 and 1 for those two states, followed by all 256 payloads. Both use `UINT16_MAX` as the out-of-domain error result.

| Logical value | Explicit tag | Dense |
|---|---:|---:|
| Absent | 0 | 0 |
| Present-empty | 256 | 1 |
| Present byte 0 | 512 | 2 |
| Present byte 255 | 767 | 257 |

Independent Python inventories predict both mappings. For each of four native builds and two layouts, the runner compares the encoder and decoder over all 65,536 input words and verifies the exact re-encoding of all 258 accepted codes. Each layout rejects 65,278 words and 65,278 out-of-domain ordinals. All four builds agree with both inventories. [Exhaustive comparison receipts](NESTED-OPTIONAL-BYTE-01/evidence.json)

Only words 0 and 256 occur in both valid code sets. Word 0 means absent in both. Word 256 means present-empty in the explicit-tag profile and present byte 254 in the dense profile. Passing a value across these boundaries without the agreed layout can therefore change a valid value into a different valid value. Strict decoding alone cannot distinguish that collision. The test supplies a concrete reason to bind a layout identifier to a public interface or call contract.

The study covers a C11 scalar bridge invoked from CPython on x86-64 Linux. The words in the table are numeric values. The fixture defines no memory byte order for network or file storage. It leaves other payload types, targets and calling conventions, LLMLang type and layout selection, and versioned ABI migration open. [Type and data model issue](https://github.com/aivibeflow/LLMLang/issues/324)

## Reproduction

Use CPython 3.12.14, GCC 14.2.0 (Debian 14.2.0-19), and Clang 23.1.1 at revision `6dfe1677ab8dffbc6ec13d53a1e0215d75147689` as recorded in the receipt. The runner compiles each bridge at `-O0` and `-O2`. Hash seeds 1 and 2 produce identical receipts.

```bash
fixture=research/language-design/RT-04/NESTED-OPTIONAL-BYTE-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" --clang /path/to/pinned/clang > /tmp/llmlang-rt04-nested-optional.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt04-nested-optional.json
```
