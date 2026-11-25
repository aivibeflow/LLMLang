# RT-10 — Wait notifications, work readiness and cancellation

What does a successful condition-variable wait establish about available work? This native fixture compares a one-shot interpretation of a wakeup with predicate checks under the shared mutex and two policies for simultaneous work and cancellation. The branch baseline is `55dfe65786080d4db00da727223f75d5c0bc2056`. [Runtime threads and synchronization](POSIX-RUNTIME-ARCHITECTURE.md)

One worker waits for an item or cancellation. A channel records the phase at which the worker is about to release the shared mutex and wait. The controller then acquires that mutex before publishing work, cancellation, or a notification that changes neither predicate. For the irrelevant-notification case, the controller waits for a second entry under the new phase before publishing work. The phases are fixture coordination and carry no runtime authorization. [Native probe](WAIT-PREDICATES-01/wait.rs) · [Rust condition variables](https://doc.rust-lang.org/1.85.1/std/sync/struct.Condvar.html)

| Controlled scenario | Observed disposition |
|---|---|
| One-shot worker receives irrelevant notification | Reports work on an empty slot |
| Predicate worker receives irrelevant notification, then work | Observably waits again before consuming one item |
| Work published before the worker enters its wait | Consumes the already present item |
| Cancellation with no work | Cancels, consumes nothing |
| Both predicates true, cancel-first policy | Cancels, leaves the item pending |
| Both predicates true, work-first policy | Consumes the item, keeps cancellation recorded |

Both optimization levels produce the same six observations. A wakeup only prompts the worker to examine the state. The work and cancellation conditions decide whether it can proceed. The simultaneous cases require an explicit choice because both predicates hold under one mutex acquisition. [Evidence from both builds](WAIT-PREDICATES-01/evidence.json)

The fixture covers one worker, one controller and a single item. It injects a notification without work and makes no claim about the frequency of spontaneous wakeups. Multiple waiters, timeout ordering, fairness, ownership of the pending item after cancellation and integration with an actual LLMLang scheduler remain open. [Runtime architecture issue](https://github.com/aivibeflow/LLMLang/issues/325)

## Reproduction

Use rustc 1.85.1 at commit `4eb161250e340c8f48f66e2b929ef4a5bed7c181`, LLVM 19.1.7 and CPython 3.12.14 on x86-64 Linux. The runner compares the native dispositions at optimization levels 0 and 2. Hash seeds 1 and 2 produced identical receipts.

```bash
fixture=research/runtime-and-systems/RT-10/WAIT-PREDICATES-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" --rustc /path/to/pinned/rustc > /tmp/llmlang-rt10-wait-predicates.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt10-wait-predicates.json
```
