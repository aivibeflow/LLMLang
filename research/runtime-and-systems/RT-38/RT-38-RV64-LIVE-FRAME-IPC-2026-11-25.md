# Live frame replacement during a blocked RV64 IPC wait

[GitHub #441](https://github.com/aivibeflow/LLMLang/issues/441) · 2026-11-25

The guest extends the timer and endpoint experiment with a data page at one stable user virtual address. The receiver sees the old frame's marker and then blocks under generation 1. The sender runs under a different Sv39 root, faults on the same virtual address, receives a timer interrupt, and requests revocation. Only the receiver's root contains the data mapping.

The machine handler checks the waiting endpoint and the old page-table entry. It advances the endpoint generation, removes the mapping and performs a local translation fence. It clears the replacement frame before setting its publication flag and installing the replacement page-table entry. A second translation fence precedes completing cancellation and making the receiver runnable. The sender later receives the stale-generation result. On resumption, the receiver checks its cancellation disposition and all 512 words of the replacement page. Both tasks retain their independent stack canaries.

| Guest configuration | UART result |
| --- | --- |
| Sanitize and publish the exact replacement frame before wakeup | `WIBCARba!` |
| Publish the dirty replacement frame | `WIBCM` |
| Publish the old frame again | `WIBCO` |
| Wake while the replacement mapping is absent | `WIBCF` |

`I` is the sender's expected private-page fault. `M` and `O` distinguish the dirty replacement and old-frame markers. `F` is the receiver's expected missing-page fault control, checked against the exact address and interrupted load. The normal path settles revocation, retrieves a later timer credit and refuses the stale sender before both tasks complete.

All four images preserve identical user bytes. The runner checks the physical frame positions, linked local fence count, absence of relocations and no hosted imports. The proof models for quiescence and composed IPC supply separate invariant evidence. This QEMU fixture uses a bounded one-use replacement slot with one runnable mutator and one blocked lease. Physical-hart ordering, remote shootdown, concurrent allocators, device ownership and DMA remain open. [Frame quiescence model](RT-38-LIVE-FRAME-QUIESCENCE-2026-11-25.md) · [Composed IPC and mapping model](RT-38-COMPOSED-MAPPING-AND-IPC-2026-11-25.md)

## Replay

Use CPython 3.12.14, LLVM/LLD 19.1.7 and the recorded QEMU 10.0.13 RV64 `virt` profile with one hart and a fixed virtual instruction clock.

```sh
fixture=research/runtime-and-systems/RT-38/RV64-LIVE-FRAME-IPC-01
python -B "$fixture/run.py" --qemu /path/to/qemu-system-riscv64 \
  --output /tmp/rt38-live-frame-ipc.json
cmp "$fixture/evidence.json" /tmp/rt38-live-frame-ipc.json
```

Two complete replays produced identical [evidence ledgers](RV64-LIVE-FRAME-IPC-01/evidence.json). Use `--qemu-data` if QEMU's machine data is outside its default directory.
