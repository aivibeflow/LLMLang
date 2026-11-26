use linux_syscalls_provider::*;
use std::ffi::c_ulong;
use std::os::fd::{AsFd, BorrowedFd};
use std::process::Command;
use std::ptr;
use std::sync::mpsc;
use std::time::Duration;

const SENTINEL: EpollEvent = EpollEvent {
    events: 0x1234_5678,
    data: 0x2345_6789_4567_8901,
};

#[test]
fn epoll_pwait_variants_preserve_timeouts_and_ready_prefix() {
    let poller = epoll_create1(0).unwrap();
    let eventfd = eventfd2(0, O_NONBLOCK).unwrap();
    let watched = EpollEvent {
        events: EPOLLIN,
        data: 0x87_65_43_21_00_01_02_03,
    };
    epoll_ctl(poller.as_fd(), eventfd.as_fd(), EpollControl::Add(watched)).unwrap();
    let mut events = [SENTINEL; 3];
    assert_eq!(epoll_pwait(poller.as_fd(), &mut events, 0).unwrap(), 0);
    assert_eq!(epoll_pwait(poller.as_fd(), &mut events, 1).unwrap(), 0);
    assert_eq!(
        epoll_pwait2(poller.as_fd(), &mut events, Some(Timespec::default())).unwrap(),
        0
    );
    assert_eq!(
        epoll_pwait2(
            poller.as_fd(),
            &mut events,
            Some(Timespec::new(0, 1_000_000).unwrap())
        )
        .unwrap(),
        0
    );
    assert_eq!(events, [SENTINEL; 3]);

    assert!(matches!(
        epoll_pwait(poller.as_fd(), &mut [], 0),
        Err(SyscallError::InvalidInput(_))
    ));
    assert!(matches!(
        epoll_pwait2(poller.as_fd(), &mut [], Some(Timespec::default())),
        Err(SyscallError::InvalidInput(_))
    ));
    assert!(epoll_pwait(eventfd.as_fd(), &mut events, 0)
        .unwrap_err()
        .is_errno(EINVAL));
    let negative = Some(Timespec::new(-1, 0).unwrap());
    assert!(epoll_pwait2(poller.as_fd(), &mut events, negative)
        .unwrap_err()
        .is_errno(EINVAL));
    assert_eq!(events, [SENTINEL; 3]);

    assert_eq!(write(eventfd.as_fd(), &1_u64.to_ne_bytes()).unwrap(), 8);
    // Infinite timeout variants are ready immediately while the eventfd is full.
    assert_eq!(epoll_pwait(poller.as_fd(), &mut events, -1).unwrap(), 1);
    assert_eq!(events, [watched, SENTINEL, SENTINEL]);
    events[0] = SENTINEL;
    assert_eq!(epoll_pwait2(poller.as_fd(), &mut events, None).unwrap(), 1);
    assert_eq!(events, [watched, SENTINEL, SENTINEL]);
    close(poller).unwrap();
    close(eventfd).unwrap();
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
fn epoll_pwait_variants_preserve_event_slots_and_mask_on_eintr() {
    const TEST: &str = "epoll_pwait_variants_preserve_event_slots_and_mask_on_eintr";
    const CHILD: &str = "LLMLANG_EPOLL_PWAIT_TEST_CHILD";
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
    type Wait = fn(BorrowedFd<'_>, &mut [EpollEvent]) -> Result<usize, SyscallError>;
    let waits: [Wait; 2] = [
        |fd, events| epoll_pwait(fd, events, 1_000),
        |fd, events| epoll_pwait2(fd, events, Some(Timespec::new(1, 0).unwrap())),
    ];
    for wait in waits {
        let poller = epoll_create1(0).unwrap();
        let (ready, receive_ready) = mpsc::channel();
        let (done, receive_done) = mpsc::channel();
        let worker = std::thread::spawn(move || {
            set_one_mask(SIGUSR1, SIG_UNBLOCK);
            set_one_mask(SIGUSR2, SIG_BLOCK);
            let before = observed_mask();
            let mut events = [SENTINEL; 2];
            ready.send(unsafe { pthread_self() }).unwrap();
            let result = wait(poller.as_fd(), &mut events);
            done.send((result, events, before, observed_mask()))
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
        let (result, events, before, after) =
            observed.expect("epoll wait did not return after SIGUSR1");
        assert!(result.unwrap_err().is_errno(EINTR));
        assert_eq!(before, (0, 1));
        assert_eq!(after, before);
        assert_eq!(events, [SENTINEL; 2]);
    }
}
