# RT-26 — Linux file-size enforcement and shared live-byte settlement

- **Evidence** — Native Linux child-process replay with a serialized parent reservation fixture.
- **LLMLang baseline** — `036abba5ca0c90bf74f3e8de7039914822c33e04`.
- **Tracking** — [PLAN §5.2](../../../PLAN.md#52-execution-semantics-and-runtime-architecture) · [RT-26 resource accounting](RT-26-HIERARCHICAL-RESOURCE-ACCOUNTING-AND-ENFORCEMENT.md).

## Question and accounting unit

Can a runtime use a Linux process limit to enforce one quota shared by a task group? The experiment measures live logical bytes as the sum of the lengths of regular files still owned by the fixture. It compares Linux `RLIMIT_FSIZE`, separate budget checks against the same group snapshot, and serialized group reservation combined with a local file limit. This live-byte accounting differs from cumulative bytes written. Committed bytes in the earlier cumulative reservation model remain spent after settlement. [Prior cumulative reservation experiment](RT-26-COOPERATIVE-BUDGET-RESERVATION.md)

Each child actually writes a new regular file under a limit set only in that child. For the brokered fixture the parent admits one path, reserves its maximum size against a 4,096-byte group limit, and sets the child's file-size limit to the reservation. After the process finishes, the parent verifies the file length. It keeps that amount charged until confirmed unlink and releases any unused part of the reservation. The fixture uses fresh paths and trusted workers, with no writes outside the declared scenario.

```mermaid
flowchart LR
    A[Group admission reserves maximum length] --> C[Child receives a local file limit]
    C --> W[Write to one owned file]
    W --> T[Terminal process observation]
    T --> S[Settle to observed file length]
    S --> L[Retain charge for live file]
    L --> D[Confirmed unlink releases charge]
```

The local limit bounds length for one file. Group admission accounts for different files, workers and reservation states. Process exit provides a point at which this fixture can settle; the file may still occupy logical capacity after the process ends.

## Results

| Experiment | Observed result |
| --- | --- |
| One file, write request 6,144 bytes, limit 4,096 bytes | First write returns 4,096. The next attempt returns `EFBIG` with the signal ignored. With the default signal disposition, the next attempt terminates the child with `SIGXFSZ`. In both runs the file remains 4,096 bytes. |
| One child writes two 3,072-byte files under the same 4,096-byte limit | Both writes succeed. The files total 6,144 bytes. |
| Two children each pass a separate empty-group check and write 3,072 bytes | The files total 6,144 bytes, exceeding the desired group budget by 2,048. |
| Parent serializes reservations for two 3,072-byte requests | The second is denied while the first is pending and while its file remains live. It succeeds after the first file is unlinked. |
| Child exits with no status receipt before writing | Terminal reconciliation observes zero bytes and returns all 2,048 reserved bytes. |
| Child exits with no receipt after writing 1,536 of 2,048 reserved bytes | The parent retains 1,536 live bytes and frees 512 unused reserved bytes. |
| Child requests 3,072 bytes against its 2,048-byte reservation | A 2,048-byte short write precedes `EFBIG`. Settlement charges exactly 2,048 live bytes. |

Ten real child processes ran in each full replay. None of the brokered cases exceeded the tracked group bound. The two abrupt-exit cases use `os._exit`, so application receipt delivery is absent. [Exact outcomes and accounting states](LINUX-FILE-BUDGET-01/evidence.json)

## Implementation consequence

Linux `RLIMIT_FSIZE` is useful as a local limit inside an admitted single-file operation. A runtime that exposes shared task quotas needs a separate serialized group decision. When a worker terminates, the runtime still needs to know which resources remain live. The signal and error paths require separate observation because both can leave a partially created file. The earlier cancellation result treated release on acknowledgment as premature. Here, actual file length after termination determines the remaining charge. [Cancellation accounting](RT-26-CANCELLATION-ACCOUNTING.md)

This fixture tracks apparent file length and a fixed one-level group. Sparse regions, storage blocks, cumulative I/O, aliases or external edits, inherited descriptors, untrusted workers, parent crash recovery, nested dynamic groups, real-time latency and cross-platform behavior remain open. The ledger experiment assumes cooperative path ownership. File-size limits alone do not establish any of those broader guarantees.

## Reproduction

Use Linux 6.18.57 x86-64 and CPython 3.12.14. The probe uses the standard library and confines writes to a temporary directory. Five executions reproduced the recorded results. The existing reservation and cancellation suites also passed, with 4 and 3 tests. [Replay](LINUX-FILE-BUDGET-01/run.py)

```sh
study=research/runtime-and-systems/RT-26/LINUX-FILE-BUDGET-01
python3 -B "$study/run.py" --output /tmp/llmlang-file-budget.json
cmp "$study/evidence.json" /tmp/llmlang-file-budget.json
python3 -B -m unittest discover -s research/runtime-and-systems/PROTOTYPES/BUDGET-RESERVATION-01
python3 -B -m unittest discover -s research/runtime-and-systems/PROTOTYPES/BUDGET-CANCELLATION-01
```
