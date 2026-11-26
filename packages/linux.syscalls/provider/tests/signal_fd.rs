use linux_syscalls_provider::*;
use std::ffi::c_ulong;
use std::os::fd::AsFd;
use std::process::Command;
use std::ptr;

const SIGUSR1: i32 = 10;
const SIGUSR2: i32 = 12;
const SIG_UNBLOCK: i32 = 1;
const SIG_SETMASK: i32 = 2;

#[repr(C)]
struct LibcSignalSet {
    words: [c_ulong; 16],
}

unsafe extern "C" {
    fn signal(number: i32, disposition: usize) -> usize;
    fn siginterrupt(number: i32, interrupt: i32) -> i32;
    fn sigemptyset(set: *mut LibcSignalSet) -> i32;
    fn sigaddset(set: *mut LibcSignalSet, signal: i32) -> i32;
    fn sigismember(set: *const LibcSignalSet, signal: i32) -> i32;
    fn pthread_sigmask(how: i32, set: *const LibcSignalSet, old: *mut LibcSignalSet) -> i32;
    fn pthread_self() -> c_ulong;
    fn pthread_kill(thread: c_ulong, signal: i32) -> i32;
}

fn isolated(name: &str) -> bool {
    const CHILD: &str = "LLMLANG_SIGNAL_FD_TEST_CHILD";
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
        "isolated signal test failed: {}\n{}\n{}",
        output.status,
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    true
}

fn start_unblocked() {
    let mut set = LibcSignalSet { words: [0; 16] };
    unsafe {
        assert_eq!(sigemptyset(ptr::from_mut(&mut set)), 0);
        assert_eq!(sigaddset(ptr::from_mut(&mut set), SIGUSR1), 0);
        assert_eq!(sigaddset(ptr::from_mut(&mut set), SIGUSR2), 0);
        assert_eq!(
            pthread_sigmask(SIG_UNBLOCK, ptr::from_ref(&set), ptr::null_mut()),
            0
        );
    }
}

fn mask() -> (bool, bool) {
    let mut set = LibcSignalSet { words: [0; 16] };
    unsafe {
        assert_eq!(
            pthread_sigmask(SIG_SETMASK, ptr::null(), ptr::from_mut(&mut set)),
            0
        );
        (
            sigismember(ptr::from_ref(&set), SIGUSR1) == 1,
            sigismember(ptr::from_ref(&set), SIGUSR2) == 1,
        )
    }
}

#[test]
fn signal_scope_restores_thread_mask_and_preserves_nesting() {
    if isolated("signal_scope_restores_thread_mask_and_preserves_nesting") {
        return;
    }
    start_unblocked();
    assert_eq!(mask(), (false, false));
    let value = rt_sigprocmask(UserSignals::USER1, |_| {
        assert_eq!(mask(), (true, false));
        rt_sigprocmask(UserSignals::BOTH, |_| assert_eq!(mask(), (true, true))).unwrap();
        assert_eq!(mask(), (true, false));
        42
    })
    .unwrap();
    assert_eq!(value, 42);
    assert_eq!(mask(), (false, false));

    let interrupted = std::panic::catch_unwind(|| {
        rt_sigprocmask(UserSignals::USER2, |_| {
            assert_eq!(mask(), (false, true));
            panic!("verify scoped restoration on unwind");
        })
        .unwrap();
    });
    assert!(interrupted.is_err());
    assert_eq!(mask(), (false, false));
}

#[test]
fn signalfd_delivers_targeted_signal_without_unblocking() {
    if isolated("signalfd_delivers_targeted_signal_without_unblocking") {
        return;
    }
    start_unblocked();
    rt_sigprocmask(UserSignals::BOTH, |scope| {
        let fd = signalfd4(scope).unwrap();
        assert_eq!(fcntl_getfd(fd.as_fd()).unwrap() & 1, 1);
        assert_eq!(fcntl_getfl(fd.as_fd()).unwrap() & O_NONBLOCK, O_NONBLOCK);
        assert!(signalfd_read(&fd).unwrap_err().is_errno(EAGAIN));
        for (number, signal) in [(SIGUSR1, UserSignal::User1), (SIGUSR2, UserSignal::User2)] {
            assert_eq!(unsafe { pthread_kill(pthread_self(), number) }, 0);
            let mut entry = [PollEntry::new(fd.as_fd(), POLLIN)];
            assert_eq!(poll(&mut entry, 0).unwrap(), 1);
            assert_eq!(entry[0].returned() & POLLIN, POLLIN);
            let event = signalfd_read(&fd).unwrap();
            assert_eq!(event.signal, signal);
            assert_eq!(event.code, -6); // SI_TKILL
            assert_eq!(event.pid, std::process::id());
            assert_eq!(event.uid, getuid().unwrap());
            assert_eq!(mask(), (true, true));
        }
        assert!(signalfd_read(&fd).unwrap_err().is_errno(EAGAIN));
        fd.close().unwrap();
    })
    .unwrap();
    assert_eq!(mask(), (false, false));
}

#[test]
fn legacy_signalfd_preserves_native_flags_and_consumes_pending_signal() {
    if isolated("legacy_signalfd_preserves_native_flags_and_consumes_pending_signal") {
        return;
    }
    start_unblocked();
    rt_sigprocmask(UserSignals::USER1, |scope| {
        let fd = signalfd(scope).unwrap();
        assert_eq!(fcntl_getfd(fd.as_fd()).unwrap() & 1, 0);
        assert_eq!(fcntl_getfl(fd.as_fd()).unwrap() & O_NONBLOCK, 0);
        let mut watched = [PollEntry::new(fd.as_fd(), POLLIN)];
        assert_eq!(poll(&mut watched, 0).unwrap(), 0);
        assert_eq!(rt_sigpending(scope).unwrap(), PendingUserSignals::default());
        assert_eq!(unsafe { pthread_kill(pthread_self(), SIGUSR1) }, 0);
        let pending = PendingUserSignals {
            user1: true,
            user2: false,
        };
        assert_eq!(rt_sigpending(scope).unwrap(), pending);
        assert_eq!(rt_sigpending(scope).unwrap(), pending);
        assert_eq!(poll(&mut watched, 0).unwrap(), 1);
        assert_eq!(watched[0].returned() & POLLIN, POLLIN);
        let event = signalfd_read_blocking(&fd).unwrap();
        assert_eq!(event.signal, UserSignal::User1);
        assert_eq!(event.code, -6); // SI_TKILL
        assert_eq!(event.pid, std::process::id());
        assert_eq!(rt_sigpending(scope).unwrap(), PendingUserSignals::default());
        assert_eq!(mask(), (true, false));
        fd.close().unwrap();
    })
    .unwrap();
    assert_eq!(mask(), (false, false));
}

#[test]
fn pending_signals_are_filtered_by_nested_scope_without_consuming() {
    if isolated("pending_signals_are_filtered_by_nested_scope_without_consuming") {
        return;
    }
    start_unblocked();
    rt_sigprocmask(UserSignals::BOTH, |outer| {
        let fd = signalfd4(outer).unwrap();
        assert_eq!(unsafe { pthread_kill(pthread_self(), SIGUSR2) }, 0);
        let pending = PendingUserSignals {
            user1: false,
            user2: true,
        };
        assert_eq!(rt_sigpending(outer).unwrap(), pending);
        rt_sigprocmask(UserSignals::USER1, |inner| {
            assert_eq!(rt_sigpending(inner).unwrap(), PendingUserSignals::default());
            assert_eq!(mask(), (true, true));
        })
        .unwrap();
        assert_eq!(rt_sigpending(outer).unwrap(), pending);
        assert_eq!(signalfd_read(&fd).unwrap().signal, UserSignal::User2);
        assert_eq!(rt_sigpending(outer).unwrap(), PendingUserSignals::default());
        fd.close().unwrap();
    })
    .unwrap();
    assert_eq!(mask(), (false, false));
}

#[test]
fn blocking_signalfd_read_propagates_eintr() {
    const TEST: &str = "blocking_signalfd_read_propagates_eintr";
    if isolated(TEST) {
        return;
    }
    use std::sync::mpsc;
    use std::time::Duration;
    extern "C" fn handler(_: i32) {}
    unsafe {
        assert_ne!(signal(SIGUSR2, handler as *const () as usize), usize::MAX);
        assert_eq!(siginterrupt(SIGUSR2, 1), 0);
    }
    let (ready, receive_ready) = mpsc::channel();
    let (done, receive_done) = mpsc::channel();
    let worker = std::thread::spawn(move || {
        start_unblocked();
        rt_sigprocmask(UserSignals::USER1, |scope| {
            let fd = signalfd(scope).unwrap();
            ready.send(unsafe { pthread_self() }).unwrap();
            let result = signalfd_read_blocking(&fd);
            let mut watched = [PollEntry::new(fd.as_fd(), POLLIN)];
            let ready_count = poll(&mut watched, 0).unwrap();
            if ready_count != 0 {
                // Drain a fallback signal before restoring a fatal default disposition.
                signalfd_read_blocking(&fd).unwrap();
            }
            assert_eq!(rt_sigpending(scope).unwrap(), PendingUserSignals::default());
            done.send(result).unwrap();
            fd.close().unwrap();
        })
        .unwrap();
    });
    let pthread = receive_ready.recv().unwrap();
    let mut observed = None;
    for _ in 0..100 {
        let delivered = unsafe { pthread_kill(pthread, SIGUSR2) };
        if delivered != 0 && !(delivered == 3 && worker.is_finished()) {
            break;
        }
        if let Ok(result) = receive_done.recv_timeout(Duration::from_millis(5)) {
            observed = Some(result);
            break;
        }
    }
    if observed.is_none() {
        // Release a wait that silently retried the interrupt.
        unsafe { pthread_kill(pthread, SIGUSR1) };
    }
    worker.join().unwrap();
    assert!(observed
        .expect("blocked signalfd read did not return after SIGUSR2")
        .unwrap_err()
        .is_errno(EINTR));
}
