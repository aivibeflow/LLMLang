use linux_syscalls_provider::*;
use std::ffi::c_ulong;
use std::os::fd::AsFd;
use std::process::Command;
use std::ptr;
use std::sync::mpsc;
use std::time::Duration;

#[test]
fn select_variants_filter_readiness_and_count_each_set() {
    let event = eventfd2(0, O_NONBLOCK).unwrap();
    let fd = event.as_fd();
    let mut sets = SelectFdSets::new();
    sets.read.insert(fd).unwrap();
    sets.write.insert(fd).unwrap();
    sets.exceptional.insert(fd).unwrap();
    let requested = sets;

    let outcome = select(&mut sets, Some(IntervalDuration::default())).unwrap();
    assert_eq!(outcome.ready, 1);
    assert_eq!(outcome.remaining, Some(IntervalDuration::default()));
    assert!(sets.read.is_empty());
    assert!(sets.write.contains(fd));
    assert!(sets.exceptional.is_empty());

    assert_eq!(write(fd, &1_u64.to_ne_bytes()).unwrap(), 8);
    sets = requested;
    let outcome = select(&mut sets, None).unwrap();
    assert_eq!(
        outcome,
        SelectOutcome {
            ready: 2,
            remaining: None
        }
    );
    assert!(sets.read.contains(fd));
    assert!(sets.write.contains(fd));
    assert!(sets.exceptional.is_empty());

    sets = requested;
    let outcome = pselect6(&mut sets, None).unwrap();
    assert_eq!(
        outcome,
        SelectOutcome {
            ready: 2,
            remaining: None
        }
    );
    assert!(sets.read.contains(fd));
    assert!(sets.write.contains(fd));
    assert!(sets.exceptional.is_empty());
    close(event).unwrap();
}

#[test]
fn select_variants_report_finite_timeouts_and_preserve_sets_on_error() {
    let (reader, writer) = pipe2(O_NONBLOCK).unwrap();
    let mut waiting = SelectFdSets::new();
    waiting.read.insert(reader.as_fd()).unwrap();
    let requested = waiting;

    let timeout = IntervalDuration::new(0, 3_000).unwrap();
    let timed = select(&mut waiting, Some(timeout)).unwrap();
    assert_eq!(timed.ready, 0);
    assert!(waiting.read.is_empty());
    assert!(
        matches!(timed.remaining, Some(value) if value == IntervalDuration::default() || value == timeout)
    );

    waiting = requested;
    let timeout = Timespec::new(0, 3_000_000).unwrap();
    let timed = pselect6(&mut waiting, Some(timeout)).unwrap();
    assert_eq!(timed.ready, 0);
    assert!(waiting.read.is_empty());
    assert!(
        matches!(timed.remaining, Some(value) if value == Timespec::default() || value == timeout)
    );

    waiting = requested;
    let invalid = Timespec::new(-1, 0).unwrap();
    let failure = pselect6(&mut waiting, Some(invalid)).unwrap_err();
    assert!(failure.error.is_errno(EINVAL));
    assert_eq!(failure.remaining, Some(invalid));
    assert_eq!(waiting, requested);
    assert_eq!(
        select(&mut SelectFdSets::new(), Some(IntervalDuration::default()))
            .unwrap()
            .ready,
        0
    );
    assert_eq!(
        pselect6(&mut SelectFdSets::new(), Some(Timespec::default()))
            .unwrap()
            .ready,
        0
    );
    close(writer).unwrap();
    close(reader).unwrap();
}

const SIGUSR1: i32 = 10;
const SIGUSR2: i32 = 12;
const SIG_BLOCK: i32 = 0;
const SIG_UNBLOCK: i32 = 1;
const SIG_SETMASK: i32 = 2;

#[repr(C)]
struct LibcSignalSet {
    words: [c_ulong; 16],
}

unsafe extern "C" {
    fn signal(number: i32, disposition: usize) -> usize;
    fn pthread_self() -> c_ulong;
    fn pthread_kill(thread: c_ulong, number: i32) -> i32;
    fn sigemptyset(set: *mut LibcSignalSet) -> i32;
    fn sigaddset(set: *mut LibcSignalSet, signal: i32) -> i32;
    fn sigismember(set: *const LibcSignalSet, signal: i32) -> i32;
    fn pthread_sigmask(how: i32, set: *const LibcSignalSet, old: *mut LibcSignalSet) -> i32;
}

fn set_one_mask(signal: i32, mode: i32) {
    let mut set = LibcSignalSet { words: [0; 16] };
    unsafe {
        assert_eq!(sigemptyset(ptr::from_mut(&mut set)), 0);
        assert_eq!(sigaddset(ptr::from_mut(&mut set), signal), 0);
        assert_eq!(
            pthread_sigmask(mode, ptr::from_ref(&set), ptr::null_mut()),
            0
        );
    }
}

fn observed_mask() -> (i32, i32) {
    let mut set = LibcSignalSet { words: [0; 16] };
    unsafe {
        assert_eq!(
            pthread_sigmask(SIG_SETMASK, ptr::null(), ptr::from_mut(&mut set)),
            0
        );
        (
            sigismember(ptr::from_ref(&set), SIGUSR1),
            sigismember(ptr::from_ref(&set), SIGUSR2),
        )
    }
}

#[test]
fn select_variants_return_remaining_timeout_and_keep_mask_on_eintr() {
    const TEST: &str = "select_variants_return_remaining_timeout_and_keep_mask_on_eintr";
    const CHILD: &str = "LLMLANG_FD_SELECT_TEST_CHILD";
    if std::env::var_os(CHILD).is_none() {
        let output = Command::new(std::env::current_exe().unwrap())
            .args(["--exact", TEST, "--nocapture"])
            .env(CHILD, "1")
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "{}\n{}",
            String::from_utf8_lossy(&output.stdout),
            String::from_utf8_lossy(&output.stderr)
        );
        return;
    }
    extern "C" fn handler(_: i32) {}
    assert_ne!(
        unsafe { signal(SIGUSR1, handler as *const () as usize) },
        usize::MAX
    );
    for nanoseconds in [false, true] {
        let (reader, writer) = pipe2(O_NONBLOCK).unwrap();
        let (ready, receive_ready) = mpsc::channel();
        let (done, receive_done) = mpsc::channel();
        let worker = std::thread::spawn(move || {
            set_one_mask(SIGUSR1, SIG_UNBLOCK);
            set_one_mask(SIGUSR2, SIG_BLOCK);
            let before = observed_mask();
            let mut sets = SelectFdSets::new();
            sets.read.insert(reader.as_fd()).unwrap();
            let requested = sets;
            ready.send(unsafe { pthread_self() }).unwrap();
            let (error, remaining) = if nanoseconds {
                let failed = pselect6(&mut sets, Some(Timespec::new(2, 0).unwrap())).unwrap_err();
                (
                    failed.error,
                    failed
                        .remaining
                        .map(|value| (value.seconds(), value.nanos())),
                )
            } else {
                let failed =
                    select(&mut sets, Some(IntervalDuration::new(2, 0).unwrap())).unwrap_err();
                (
                    failed.error,
                    failed
                        .remaining
                        .map(|value| (value.seconds(), value.micros() * 1_000)),
                )
            };
            done.send((error, remaining, sets == requested, before, observed_mask()))
                .unwrap();
        });
        let pthread = receive_ready.recv().unwrap();
        let mut observed = None;
        for _ in 0..100 {
            let sent = unsafe { pthread_kill(pthread, SIGUSR1) };
            assert!(sent == 0 || (sent == 3 && worker.is_finished()));
            if let Ok(value) = receive_done.recv_timeout(Duration::from_millis(5)) {
                observed = Some(value);
                break;
            }
        }
        worker.join().unwrap();
        close(writer).unwrap();
        let (error, remaining, unchanged, before, after) =
            observed.expect("select wait did not return after SIGUSR1");
        assert!(error.is_errno(EINTR));
        assert!(unchanged);
        assert_eq!(before, (0, 1));
        assert_eq!(after, before);
        assert!(matches!(remaining, Some(value) if ((0, 0)..=(2, 0)).contains(&value)));
    }
}
