use linux_syscalls_provider::*;
use std::time::{Duration, Instant};

#[test]
fn posix_timer_updates_settings_and_expires_without_notifications() {
    let timer = timer_create(CLOCK_MONOTONIC).unwrap();
    assert_eq!(timer_gettime(&timer).unwrap(), TimerSpec::default());
    assert_eq!(timer_getoverrun(&timer).unwrap(), 0);
    let once = TimerSpec {
        interval: Timespec::default(),
        initial: Timespec::new(0, 3_000_000).unwrap(),
    };
    assert_eq!(
        timer_settime(&timer, TimerMode::Relative, once).unwrap(),
        TimerSpec::default()
    );
    let until = Instant::now() + Duration::from_secs(1);
    loop {
        let observed = timer_gettime(&timer).unwrap();
        assert_eq!(observed.interval, Timespec::default());
        if observed.initial == Timespec::default() {
            break;
        }
        assert!(Instant::now() < until, "one-shot timer did not expire");
        std::thread::yield_now();
    }
    assert_eq!(timer_getoverrun(&timer).unwrap(), 0);
    timer_delete(timer).unwrap();
}

#[test]
fn posix_timer_disarms_and_preserves_kernel_errors() {
    assert!(timer_create(i32::MAX).unwrap_err().is_errno(EINVAL));
    let timer = timer_create(CLOCK_MONOTONIC).unwrap();
    let initial = clock_gettime(CLOCK_MONOTONIC).unwrap();
    let recurring = TimerSpec {
        interval: Timespec::new(2, 500_000).unwrap(),
        initial: Timespec::new(initial.seconds() + 30, initial.nanos()).unwrap(),
    };
    assert_eq!(
        timer_settime(&timer, TimerMode::Absolute, recurring).unwrap(),
        TimerSpec::default()
    );
    assert_eq!(timer_gettime(&timer).unwrap().interval, recurring.interval);
    let invalid = TimerSpec {
        initial: Timespec::new(-1, 0).unwrap(),
        ..recurring
    };
    assert!(timer_settime(&timer, TimerMode::Relative, invalid)
        .unwrap_err()
        .is_errno(EINVAL));
    assert_eq!(timer_gettime(&timer).unwrap().interval, recurring.interval);
    let previous = timer_settime(&timer, TimerMode::Absolute, TimerSpec::default()).unwrap();
    assert_eq!(previous.interval, recurring.interval);
    let disarmed = timer_gettime(&timer).unwrap();
    assert_eq!(disarmed.interval, Timespec::default());
    // Some native SIGEV_NONE versions report a stale expiry on disarm.
    assert!(
        (disarmed.initial.seconds(), disarmed.initial.nanos())
            <= (previous.initial.seconds(), previous.initial.nanos())
    );
    assert_eq!(timer_getoverrun(&timer).unwrap(), 0);
}
