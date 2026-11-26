use linux_syscalls_provider::*;
use std::ffi::c_ulong;
use std::process::Command;
use std::ptr;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

const SIGALRM: i32 = 14;
const SIGVTALRM: i32 = 26;
const SIGPROF: i32 = 27;
const SIG_IGN: usize = 1;
const SIG_UNBLOCK: i32 = 1;

#[repr(C)]
struct LibcSignalSet {
    words: [c_ulong; 16],
}

unsafe extern "C" {
    fn signal(number: i32, disposition: usize) -> usize;
    fn sigemptyset(set: *mut LibcSignalSet) -> i32;
    fn sigaddset(set: *mut LibcSignalSet, signal: i32) -> i32;
    fn pthread_sigmask(how: i32, set: *const LibcSignalSet, old: *mut LibcSignalSet) -> i32;
}

fn isolated(name: &str) -> bool {
    const CHILD: &str = "LLMLANG_LEGACY_TIMER_TEST_CHILD";
    if std::env::var(CHILD).as_deref() == Ok(name) {
        return false;
    }
    let output = Command::new(std::env::current_exe().unwrap())
        .args(["--exact", name, "--nocapture"])
        .env(CHILD, name)
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "isolated timer test failed: {}\n{}\n{}",
        output.status,
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    true
}

fn ignore_timer_signals() {
    for number in [SIGALRM, SIGVTALRM, SIGPROF] {
        assert_ne!(unsafe { signal(number, SIG_IGN) }, usize::MAX);
    }
}

#[test]
fn interval_timers_observe_previous_settings_and_disarm() {
    if isolated("interval_timers_observe_previous_settings_and_disarm") {
        return;
    }
    ignore_timer_signals();
    assert!(IntervalDuration::new(-1, 0).is_err());
    assert!(IntervalDuration::new(0, 1_000_000).is_err());
    let request = IntervalSettings {
        interval: IntervalDuration::new(2, 875_000).unwrap(),
        remaining: IntervalDuration::new(120, 125_000).unwrap(),
    };
    for timer in [
        IntervalTimer::Real,
        IntervalTimer::Virtual,
        IntervalTimer::Profile,
    ] {
        assert_eq!(getitimer(timer).unwrap(), IntervalSettings::default());
        assert_eq!(
            setitimer(timer, request).unwrap(),
            IntervalSettings::default()
        );
        let set = getitimer(timer).unwrap();
        assert_eq!(set.interval, request.interval);
        assert!((1..=121).contains(&set.remaining.seconds()));
        assert_eq!(
            setitimer(timer, IntervalSettings::default())
                .unwrap()
                .interval,
            request.interval
        );
        assert_eq!(getitimer(timer).unwrap(), IntervalSettings::default());
    }
}

#[test]
fn alarm_and_real_interval_timer_share_state() {
    if isolated("alarm_and_real_interval_timer_share_state") {
        return;
    }
    ignore_timer_signals();
    assert_eq!(alarm(120).unwrap(), 0);
    let setting = getitimer(IntervalTimer::Real).unwrap();
    assert_eq!(setting.interval, IntervalDuration::default());
    assert!((1..=120).contains(&setting.remaining.seconds()));
    assert!((1..=120).contains(&alarm(0).unwrap()));
    assert_eq!(
        getitimer(IntervalTimer::Real).unwrap(),
        IntervalSettings::default()
    );
}

#[test]
fn interval_timer_signals_are_observed_in_isolated_process() {
    if isolated("interval_timer_signals_are_observed_in_isolated_process") {
        return;
    }
    ignore_timer_signals();
    static SEEN: AtomicBool = AtomicBool::new(false);
    extern "C" fn record(_: i32) {
        SEEN.store(true, Ordering::Relaxed);
    }
    assert_ne!(
        unsafe { signal(SIGALRM, record as *const () as usize) },
        usize::MAX
    );
    let mut set = LibcSignalSet { words: [0; 16] };
    unsafe {
        assert_eq!(sigemptyset(ptr::from_mut(&mut set)), 0);
        assert_eq!(sigaddset(ptr::from_mut(&mut set), SIGALRM), 0);
        assert_eq!(
            pthread_sigmask(SIG_UNBLOCK, ptr::from_ref(&set), ptr::null_mut()),
            0
        );
    }
    let request = IntervalSettings {
        interval: IntervalDuration::default(),
        remaining: IntervalDuration::new(0, 5_000).unwrap(),
    };
    setitimer(IntervalTimer::Real, request).unwrap();
    let end = Instant::now() + Duration::from_secs(2);
    while !SEEN.load(Ordering::Relaxed) && Instant::now() < end {
        std::thread::sleep(Duration::from_millis(1));
    }
    alarm(0).unwrap();
    assert!(SEEN.load(Ordering::Relaxed));
    assert_eq!(
        getitimer(IntervalTimer::Real).unwrap(),
        IntervalSettings::default()
    );
}

#[test]
fn process_times_exposes_elapsed_and_accounted_ticks() {
    let before = times().unwrap();
    let began = Instant::now();
    let mut sum = 0_u64;
    while began.elapsed() < Duration::from_millis(25) {
        sum = std::hint::black_box(sum.wrapping_add(1));
    }
    let after = times().unwrap();
    assert!(after.elapsed.wrapping_sub(before.elapsed) > 0);
    assert!(after.user.wrapping_sub(before.user) >= 0);
    assert!(after.system.wrapping_sub(before.system) >= 0);
    assert!(after.children_user.wrapping_sub(before.children_user) >= 0);
    assert!(after.children_system.wrapping_sub(before.children_system) >= 0);
}
