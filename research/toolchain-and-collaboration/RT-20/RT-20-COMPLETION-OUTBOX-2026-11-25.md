# RT-20. Exact completion across SQLite, Git and filesystem export

This fixture reconciles the RT-20 completion gate with the RT-19 outbox model, RT-24 native Git publication and atomic filesystem export. The Change Impact Plan must pass before SQLite stores a prepared request. Git publishes the exact candidate with its receipt. The exporter reads the original accepted commit from that receipt, writes a complete generation and then switches the current pointer. [Issue #338](https://github.com/aivibeflow/LLMLang/issues/338) · [RT-19 SQLite and Git recovery](../RT-19/RT-19-SQLITE-GIT-PROCESS-RECOVERY-2026-11-24.md) · [Git CIP recovery](../RT-24/RT-24-CIP-RECOVERY-2026-11-25.md)

The SQLite row binds the request key and immutable plan, tree and parent identities. It distinguishes a prepared job, an accepted Git commit and an exported result. The export generation contains both exact Git source files and a receipt with their SHA-256 digests. Existing bytes are verified before reusing a generation. The protocol advances each store in order and recovers by cross-checking the exact receipts.

```mermaid
flowchart LR
    A[Validate exact Change Impact Plan] --> B[Persist prepared request in SQLite]
    B --> C[Publish exact Git commit and receipt]
    C --> D[Record committed identity in SQLite]
    D --> E[Stage immutable export generation]
    E --> F[Switch current pointer]
    F --> G[Record exported outcome]
```

## Results

| Process exits immediately after | SQLite observation | Git receipt | Export pointer |
| --- | --- | --- | --- |
| Insert before SQLite commit | Absent | Absent | Absent |
| Prepared SQLite commit | Prepared | Absent | Absent |
| Git ref transaction | Prepared | Present | Absent |
| Recording the Git outcome | Git accepted | Present | Absent |
| Staging the complete file generation | Git accepted | Present | Absent |
| Switching the current pointer | Git accepted | Present | Present |

All six interrupted runs and the ordinary run recover one identical commit and one published export generation. After interruption with a visible Git receipt, the driver advances the branch to a different tree before recovery. The export still contains the original accepted bytes. An exact retry returns the same result. Reusing the operation key for a different plan refuses, and an externally changed generation fails verification. [Process-boundary and identity ledger](COMPLETION-OUTBOX-01/evidence.json)

The fixture tests local process termination and recovery across real SQLite WAL, Git refs and filesystem renames. The execution schedule has one active recovery worker per operation. Production worker leasing, remote Git and filesystem semantics, power loss, reader retention, rollback across externally owned stores and authorization remain open.

## Replay

Source baseline `e06c2de` on `research/all`. Replay used Git 2.56.1, SQLite 3.53.1 and CPython 3.12.14 on Linux. Each temporary Git repository uses branch `research/all`. Run from the repository root.

```sh
data=research/toolchain-and-collaboration/RT-20/COMPLETION-OUTBOX-01
receipt=$(mktemp)
python -B "$data/run.py" "$receipt"
cmp "$data/evidence.json" "$receipt"
rm "$receipt"
```
