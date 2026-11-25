# RT-10 — Release sequences from explicit modification order

When does an acquire that reads the value 1 synchronize with a particular earlier release? This fixture extends [Scenario 114](../../language-design/RT-04/RESEARCH-SCENARIO-114-RELEASE-SEQUENCES-AND-ACQUIRE-RELAY.md) by deriving membership from the selected modification order and exact read-from edge. The branch baseline is `170af3d71c1e8ce8e33bf6506ff381181eb27038`. [C++20 rule change](https://open-std.org/jtc1/sc22/wg21/docs/papers/2018/p0982r1.html)

The atomic flag starts at zero. Its writers perform one release store, a following relaxed store by that writer, a relaxed store by a second writer, and two independent relaxed read-modify-write operations. Each store writes 1. Each RMW adds zero to the value of its predecessor in modification order. The runner enumerates every total order consistent with the release writer's program order, then selects the initial value or one of the five modifications as the acquire's exact source.

A forward scan derives the maximal contiguous release sequence under each version's rule. A separate membership check examines the interval from the release head to the selected acquire source. C++17 admits subsequent same-thread stores and RMW operations in that interval. C++20 requires RMW operations after the head. An independent relaxed store by another thread breaks the sequence in both profiles. [Forward scanner and interval check](RELEASE-SEQUENCE-MEMBERSHIP-01/run.py) · [Current C++ working draft](https://eel.is/c++draft/intro.multithread)

| Selected acquire source | Numeric flag | Release edge in C++17 | Release edge in C++20 |
|---|---:|---|---|
| Directly from the release | 1 | Yes | Yes |
| RMW after the release and earlier RMW | 1 | Yes | Yes |
| RMW after the release writer's relaxed store | 1 | Yes | No |
| RMW after another writer's relaxed store | 1 | No | No |

Both algorithms agree across 60 modification orders and 360 selected read-from cases. They derive the edge in 150 cases under C++17 and 90 under C++20. The shortcut that treats a numeric value of 1 as proof of that edge gives 120 unsupported edges under C++17 and 180 under C++20. In the fixture where the release writer also writes an atomic payload before publishing the flag, the derived edge rules out the initial payload. When there is no edge, this check leaves the initial payload in the candidate set. [Full counts and exact witness orders](RELEASE-SEQUENCE-MEMBERSHIP-01/evidence.json)

The fixture operates on explicitly supplied modification order and read-from relations. It tests membership under the two versioned rules and assumes the remaining ordering conditions of its witness. It does not enumerate complete C++ executions, validate native compiler or hardware behavior, or select the LLMLang memory model. [Runtime architecture issue](https://github.com/aivibeflow/LLMLang/issues/325)

## Reproduction

CPython 3.12.14 yielded identical receipts with hash seeds 1 and 2.

```bash
fixture=research/runtime-and-systems/RT-10/RELEASE-SEQUENCE-MEMBERSHIP-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > /tmp/llmlang-rt10-release-sequence.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt10-release-sequence.json
```
