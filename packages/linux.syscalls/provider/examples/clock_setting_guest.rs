use linux_syscalls_provider::{
    clock_gettime, clock_settime, getppid, gettimeofday, settimeofday, setuid, Timespec, Timeval,
    UserId, CLOCK_MONOTONIC, CLOCK_REALTIME, EINVAL,
};
use std::error::Error;

const GUEST_ARGUMENT: &str = "--llmlang-disposable-guest-probe";
const NANOS_PER_SECOND: i128 = 1_000_000_000;

fn nanos(value: Timespec) -> i128 {
    i128::from(value.seconds()) * NANOS_PER_SECOND + i128::from(value.nanos())
}

fn from_nanos(value: i128) -> Result<Timespec, Box<dyn Error>> {
    Ok(Timespec::new(
        i64::try_from(value.div_euclid(NANOS_PER_SECOND))?,
        i64::try_from(value.rem_euclid(NANOS_PER_SECOND))?,
    )?)
}

struct RestoreRealtime {
    realtime: i128,
    monotonic: i128,
    active: bool,
}

impl RestoreRealtime {
    fn time_now(&self) -> Result<Timespec, Box<dyn Error>> {
        let elapsed = nanos(clock_gettime(CLOCK_MONOTONIC)?) - self.monotonic;
        from_nanos(self.realtime + elapsed)
    }

    fn restore(&mut self) -> Result<Timespec, Box<dyn Error>> {
        let value = self.time_now()?;
        clock_settime(value)?;
        self.active = false;
        Ok(value)
    }
}

impl Drop for RestoreRealtime {
    fn drop(&mut self) {
        if self.active {
            let _ = self.restore();
        }
    }
}

fn assert_observed_at_or_after(target: i128, observed: i128) {
    assert!((0..5 * NANOS_PER_SECOND).contains(&(observed - target)));
}

fn assert_clock_step(target: i128, observed: i128, started: i128) -> Result<(), Box<dyn Error>> {
    let elapsed = nanos(clock_gettime(CLOCK_MONOTONIC)?) - started;
    // Allow a small margin for timekeeping quantization.
    assert!((0..=elapsed + 1_000_000).contains(&(observed - target)));
    Ok(())
}

fn main() -> Result<(), Box<dyn Error>> {
    assert!(std::env::args().skip(1).eq([GUEST_ARGUMENT]));
    assert_eq!(getppid()?, 1, "run through the disposable guest init");

    let original = clock_gettime(CLOCK_REALTIME)?;
    let mut restore = RestoreRealtime {
        realtime: nanos(original),
        monotonic: nanos(clock_gettime(CLOCK_MONOTONIC)?),
        active: true,
    };

    let target = Timespec::new(original.seconds() + 120, 250_000_000)?;
    let started = nanos(clock_gettime(CLOCK_MONOTONIC)?);
    clock_settime(target)?;
    assert_clock_step(
        nanos(target),
        nanos(clock_gettime(CLOCK_REALTIME)?),
        started,
    )?;
    println!("LLMLANG_GUEST_CASE clock_settime_updates_disposable_realtime");

    let target = Timeval::new(original.seconds() + 240, 654_321)?;
    let started = nanos(clock_gettime(CLOCK_MONOTONIC)?);
    settimeofday(target)?;
    let observed = gettimeofday()?;
    let micros_as_nanos = |value: Timeval| {
        i128::from(value.seconds()) * NANOS_PER_SECOND + i128::from(value.micros()) * 1000
    };
    assert_clock_step(micros_as_nanos(target), micros_as_nanos(observed), started)?;
    println!("LLMLANG_GUEST_CASE settimeofday_updates_microseconds_without_timezone");

    assert!(clock_settime(Timespec::new(-1, 0)?)
        .unwrap_err()
        .is_errno(EINVAL));
    assert!(settimeofday(Timeval::new(-1, 0)?)
        .unwrap_err()
        .is_errno(EINVAL));

    assert_clock_step(
        micros_as_nanos(target),
        nanos(clock_gettime(CLOCK_REALTIME)?),
        started,
    )?;

    let restored = restore.restore()?;
    assert_observed_at_or_after(nanos(restored), nanos(clock_gettime(CLOCK_REALTIME)?));
    println!("LLMLANG_GUEST_CASE guest_realtime_restores_from_monotonic_elapsed");

    // Use otherwise valid future times after dropping privileges.
    setuid(UserId::new(65534)?)?;
    let protected = clock_gettime(CLOCK_REALTIME)?;
    assert!(clock_settime(Timespec::new(protected.seconds() + 120, 0)?)
        .unwrap_err()
        .is_errno(1));
    assert!(settimeofday(Timeval::new(protected.seconds() + 240, 0)?)
        .unwrap_err()
        .is_errno(1));
    assert_observed_at_or_after(nanos(protected), nanos(clock_gettime(CLOCK_REALTIME)?));
    println!("LLMLANG_GUEST_CASE clock_setters_preserve_invalid_and_unprivileged_errno");
    Ok(())
}
