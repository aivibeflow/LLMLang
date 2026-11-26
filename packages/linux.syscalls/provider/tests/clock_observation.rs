use linux_syscalls_provider::{
    adjtimex, clock_adjtime, clock_gettime, TimexObservation, TimexSubseconds, CLOCK_REALTIME,
};

fn realtime_sample(observation: TimexObservation) -> i128 {
    let nanos = match observation.time_fraction {
        TimexSubseconds::Microseconds(value) => i128::from(value) * 1000,
        TimexSubseconds::Nanoseconds(value) => i128::from(value),
    };
    i128::from(observation.time_seconds) * 1_000_000_000 + nanos
}

#[test]
fn native_realtime_discipline_queries_observe_clock_without_adjustment() {
    let read_realtime = || {
        let value = clock_gettime(CLOCK_REALTIME).unwrap();
        i128::from(value.seconds()) * 1_000_000_000 + i128::from(value.nanos())
    };
    let before = read_realtime();
    let legacy = adjtimex().unwrap();
    let targeted = clock_adjtime().unwrap();
    let after = read_realtime();

    // Linux can adjust the reported second at a leap transition.
    let earliest = before.min(after) - 1_000_000_001;
    let latest = before.max(after) + 1_000_000_001;
    for observation in [legacy, targeted] {
        assert!((earliest..=latest).contains(&realtime_sample(observation)));
        assert!(observation.tick > 0);
    }
}
