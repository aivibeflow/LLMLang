# Native Linux CPU timer scope and observation delay

[GitHub #332](https://github.com/aivibeflow/LLMLang/issues/332) · 2026-11-25

A worker arms a Linux POSIX CPU timer and then blocks at a barrier. Its peer runs for twice the requested CPU budget, measured by the peer's own thread clock. Both variants target the same worker's realtime signal queue using `SIGEV_THREAD_ID`. The source clock is either the process CPU clock or the worker's own thread CPU clock. The worker checks whether the signal is already pending when the peer releases the barrier. It then polls for its timer if the signal has yet to arrive.

All 60 process-clock trials report a pending signal while the target worker is still below its budget. All 60 thread-clock trials receive their signal only after the target worker itself has consumed at least the configured CPU budget. The worker's CPU time at the process-clock observation is at most 32.257 µs in this recording. Targeted signal delivery and resource charging use different scopes.

## Host measurements

The process and worker phases share one logical CPU on the recorded Linux 6.18.57 host. Each budget and scope has 20 rounds. The table shows measured CPU time above the configured amount when the worker observed its signal. In the process-clock profiles most of that excess is intentional peer work before observation.

| Configured CPU budget | Process clock excess, min / median / max | Worker clock excess, min / median / max |
| --- | ---: | ---: |
| 5 ms | 5.010 / 5.014 / 5.095 ms | 0.889 / 2.810 / 3.817 ms |
| 10 ms | 10.010 / 10.016 / 11.885 ms | 0.900 / 1.869 / 13.089 ms |
| 20 ms | 20.014 / 20.021 / 20.996 ms | 0.050 / 3.748 / 3.937 ms |

The runner retains target and peer CPU counters and wall time for each round. The worker clock supplies an exact native accounting scope, while the observed timer signal is a notification. The observed delay permits overshoot and includes the observation boundary. It supplies no hard interruption bound. Task migration, sharing a thread among coroutines, delegated enforcement, other OSes, hardware PMU counters and controlled workload acceptance remain open.

## Replay

Use CPython 3.12.14, GCC 14.2.0, glibc 2.41 and Linux. Run on an allowed logical CPU. Two independent builds reproduce the complete categorical ledger. The latency records are specific to each execution.

```sh
fixture=research/runtime-and-systems/RT-26/CPU-TIMER-SCOPE-01
taskset -c 4 python "$fixture/run.py" --output /tmp/rt26-cpu-timers.json \
  --measurements /tmp/rt26-cpu-timer-samples.json
cmp "$fixture/evidence.json" /tmp/rt26-cpu-timers.json
```

[Categorical evidence](CPU-TIMER-SCOPE-01/evidence.json) · [Raw host samples](CPU-TIMER-SCOPE-01/samples-host.json)
