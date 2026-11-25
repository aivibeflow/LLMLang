# RT-11 — Check debug column freshness under an unchanged line projection

## Question and method

Can an artifact consumer reuse exact debug evidence when the emitted code and decoded source lines are unchanged? The companion [native source metadata study](RT-11-NATIVE-SOURCE-METADATA-REUSE-2026-11-25.md) already checks line insertion and `__LINE__`. This follow-up isolates a column edit and compares the raw DWARF line program against its line-and-address projection. The baseline is `b24cc66d6cc1a87ecdfc591e6d32550c0ba40951` on `research/all`.

The two source versions implement the same unsigned 32-bit addition. They differ only in the indentation and spacing of the return line. The runner builds both with and without debug data and checks ten native calls for each build. It compares whole object and `.text` hashes, raw `.debug_line` bytes, decoded line/address pairs and the values emitted by DWARF column-change instructions. The table carries those comparisons without a separate diagram.

## Results

| Observation | Effect of the edit |
|---|---|
| No-debug object and executable text | Byte-identical. |
| Native results | All 40 calls agree with the unsigned arithmetic oracle. |
| Decoded line/address rows | Equal between the two debug objects. |
| Exact debug object and raw line program | Different. The raw column updates change from `[30, 5, 14, 1]` to `[30, 2, 13, 1]`. |

An invariant line-number projection can support a consumer that asks only for those exact line/address pairs. It cannot close an exact or column-aware debug obligation. That distinction matters for incremental source attribution even when line insertion was already accounted for. The result covers one compiler, one simple function and the selected debug projections. Debugger behavior, full ELF equivalence across programs and production projection certification remain open. [Raw hashes and observations](DEBUG-COLUMN-REUSE-01/evidence.json) · [Incremental analysis tracking](https://github.com/aivibeflow/LLMLang/issues/299)

## Reproduction

Use CPython 3.12.14, Debian GCC 14.2.0-19 and GNU Binutils 2.44 on Linux x86-64. The [runner](DEBUG-COLUMN-REUSE-01/run.py) records tool versions, source strings and exact output digests. Hash seeds 1 and 2 produced byte-identical results.

```bash
fixture=research/toolchain-and-collaboration/RT-11/DEBUG-COLUMN-REUSE-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > /tmp/llmlang-rt11-debug-column.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt11-debug-column.json
```
