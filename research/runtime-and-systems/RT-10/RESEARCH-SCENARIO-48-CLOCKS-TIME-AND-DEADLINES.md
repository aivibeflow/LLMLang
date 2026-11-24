# Research Scenario 48 — Clocks, Time, and Deadlines

**Status:** Evidence-linked prior-art comparison; no LLMLang time model selected  
**Research area:** RT-03 time observations, RT-10 timers/runtime, RT-13 portability, RT-18 reproducibility  
**Updated:** 2026-11-19

## 1. Question and scope

How should programs represent calendar instants, elapsed durations, timeouts, and scheduled wall-clock events without confusing clock adjustment, system suspend, timezone rules, and testability?

Separate:

1. Wall-clock timestamps for civil time, persistence, and cross-system exchange.
2. Monotonic instants for measuring elapsed time and deadlines inside a process.
3. Duration arithmetic and overflow limits.
4. Whether a monotonic clock advances during system suspend.
5. Timer sleep semantics, tolerance, and scheduler latency.
6. Clock injection for deterministic tests and virtual-time simulation.
7. Calendar/timezone/leap-second policy versus a uniform time scale.

This report compares Rust, Go, Swift, and Java time APIs. It does not benchmark clock precision, specify distributed clock synchronization, define a calendar library, or promise hard real-time deadlines.

## 2. Prior-art comparison

### Rust: separate opaque Instant and civil SystemTime

Rust provides Instant as an opaque measurement of a monotonically nondecreasing clock and SystemTime for system wall time. Instant values support relative measurement and comparisons but do not expose a portable epoch. The documentation notes that Instant is not guaranteed steady, and whether time spent suspended counts as elapsed varies across platforms and Rust versions. Monotonicity can be violated by platform bugs; checked operations are available to detect problematic ordering.

The separate types prevent accidentally serializing a process-local stopwatch value as a date, but callers must deliberately select a clock and handle platform limits and suspend behavior.

Sources: [Rust std::time::Instant](https://doc.rust-lang.org/std/time/struct.Instant.html), [Rust std::time](https://doc.rust-lang.org/std/time/).

### Go: one Time may carry wall and monotonic readings

Go Time returned by Now carries a wall-clock reading and a monotonic-clock reading when available. Time-telling operations use wall time; comparisons and subtraction can use the monotonic reading. Serialization and parsing omit the monotonic reading, because it is process-local and not meaningful for persisted/cross-process times. The Go documentation warns that the == operator also compares location and monotonic data, not just the instant; Equal is the intended instant comparison.

This offers convenient elapsed-time safety without a separate public stopwatch type, but the same Time value changes its comparison/subtraction semantics depending on whether it retains a monotonic component. Persistence strips that component, so elapsed-time guarantees do not survive a serialization boundary.

Source: [Go time package — Monotonic Clocks](https://pkg.go.dev/time#hdr-Monotonic_Clocks).

### Swift: Clock protocol, continuous and suspending variants

Swift defines a Clock protocol with an associated Instant and Duration, now, sleep-until, and sleep-for operations. ContinuousClock advances while the system sleeps; SuspendingClock stops while the system is asleep. Sleep accepts a tolerance, making scheduling slack explicit. This allows APIs to accept a clock abstraction and supports test clocks or alternate time sources without hard-coding a global function.

The model makes suspend policy part of the clock type. Clock protocols and associated instant types can make APIs more generic, but callers must still choose the correct clock for timeout versus active-runtime accounting.

Sources: [Swift Clock protocol](https://docs.swift.org/latest/documentation/swift/clock/), [Swift ContinuousClock](https://docs.swift.org/latest/documentation/swift/continuousclock/), [Swift SuspendingClock](https://docs.swift.org/latest/documentation/swift/suspendingclock/).

### Java: epoch Instant/Clock versus arbitrary-origin nanoTime

Java Instant represents a point on the Java Time-Scale and can be obtained from a Clock. Clock abstraction supports alternate sources for tests; calling Instant.now() without a Clock hard-codes the system source. System.nanoTime() is a separate high-resolution source for elapsed measurements only: its origin is arbitrary, values are meaningful only as differences within one JVM, and resolution is not guaranteed to equal precision. The API recommends difference-based timeout comparisons to avoid overflow when adding a deadline to a start value.

This provides a clear persisted timestamp API and a separate elapsed-time primitive. The application must thread Clock dependencies to obtain testability, and nanoTime values cannot be stored as universal instants.

Sources: [Java Instant](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/time/Instant.html), [Java Clock](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/time/Clock.html), [System.nanoTime](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/lang/System.html#nanoTime()).

## 3. Comparison matrix

| Dimension | Rust | Go | Swift | Java |
|---|---|---|---|---|
| Wall clock | SystemTime | Time wall component | Clock/Instant | Instant via Clock |
| Monotonic elapsed time | Opaque Instant | Monotonic component in Time when available | Clock-specific Instant | System.nanoTime |
| Public separation | Distinct types | Often one Time value with dual readings | Clock-associated Instant types | Separate Instant/Clock and nanoTime |
| Suspend behavior | Not specified uniformly; platform/version varies | Monotonic reading details are platform/runtime dependent | Continuous versus Suspending types | nanoTime contract excludes wall time; suspend policy requires platform-specific validation |
| Serialization | Wall SystemTime conversion is explicit and fallible | Serialization omits monotonic reading | Clock instants are clock-relative; not all instants imply epoch timestamps | Instant is intended as timeline timestamp; nanoTime origin is not serializable |
| Testability | Inject an abstraction/wrapper around time calls | Inject a clock function/interface or fake timer | Clock protocol permits alternate clocks | Clock is explicitly injectable |
| Timer tolerance | Runtime sleep APIs separate from Instant | Timer/ticker APIs in package | Clock sleep accepts tolerance | Scheduler APIs and sleep calls; no hard deadline guarantee |

Clock monotonicity is not the same as clock steadiness, precision, resolution, or scheduler punctuality. A timestamp also does not encode a timezone or calendar rule.

## 4. Discriminating fixture

Implement one timeout-based operation with an injected time source, a persisted event timestamp, and a calendar schedule:

- Start a timeout, advance wall time backward and forward while monotonic time advances normally.
- Suspend/resume the system or use a virtual clock that simulates suspend; compare continuous and suspending clocks.
- Serialize and deserialize time values and verify which operations remain meaningful.
- Compare deadline arithmetic near representational limits and avoid addition overflow.
- Change timezone database rules for a future local appointment and distinguish the stored local intent from its resolved instant.
- Advance a fake clock deterministically across timer wakeups, cancellation, and tolerance windows.

Record wall timestamp, monotonic instant, duration, deadline, timeout result, sleep overshoot, clock implementation/version, suspend policy, time-zone database version, and whether the clock was real or virtual. Keep civil scheduling outcomes separate from elapsed-time outcomes.

## 5. Cross-area implications and open hypotheses

- Wall timestamps, monotonic instants, durations, deadlines, and local calendar times are different semantic values. One generic Time type can hide important preconditions unless its operations make the clock domain explicit.
- A monotonic instant is usually process/boot/clock-domain-local; it must not be persisted, sent between processes, or compared with a timestamp from another clock domain unless the API explicitly defines that conversion.
- Deadline APIs should prefer monotonic differences or typed deadlines to avoid wall-clock changes and arithmetic overflow.
- Suspend accounting is a policy decision: a user-facing session timeout may want continuous elapsed time, while CPU/active-runtime budget may want a suspending clock.
- Testability improves when clock sources are dependencies, but a fake clock must specify how scheduled tasks wake and how equal-time events are ordered.
- Deterministic replay/proof cannot assume host wall time is stable input. Clock observations and timezone data must be modeled as explicit environment inputs.

## 6. Next research and falsifiers

Build the fixture with an injected clock on two operating systems and at least one virtual clock implementation. Measure resolution and wakeup overshoot separately from the API's semantic contract. Test suspend behavior, time adjustment, timer cancellation, serialization, and timezone-rule updates. Verify that timer deadlines and wall schedules invalidate/replay correctly when their declared environment inputs change.

A combined wall/monotonic value is weakened if its comparison semantics change unexpectedly after serialization or copying. Fully separate clocks are weakened if common timeout APIs repeatedly mix incompatible types or discard monotonic guarantees. A clock protocol is weakened if associated types make routine APIs or virtual-time testing impractical. Any model is weakened if it labels resolution as precision or claims hard real-time scheduling without runtime evidence.

No LLMLang clock type, timer policy, suspend rule, or civil-time representation is selected.

## 7. Sources and temporal limits

Official documentation was consulted 2026-11-19. Rust explicitly documents platform variation in suspend behavior; Go's monotonic reading is process-local and implementation-backed; Swift clock types make suspend policy explicit; Java distinguishes wall and elapsed-time APIs. Resolution, drift, suspend semantics, and scheduler latency require target-specific experiments.
