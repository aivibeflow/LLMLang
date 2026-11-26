use linux_syscalls_provider::*;
use std::os::fd::AsFd;
use std::os::raw::c_ulong;
use std::os::unix::thread::JoinHandleExt;
use std::sync::mpsc;
use std::thread;
use std::time::Duration;

#[test]
fn clocks_validate_subsecond_fields_and_preserve_kernel_errors() {
    let first = clock_gettime(CLOCK_MONOTONIC).unwrap();
    let resolution = clock_getres(CLOCK_MONOTONIC).unwrap();
    let second = clock_gettime(CLOCK_MONOTONIC).unwrap();
    assert!((first.seconds(), first.nanos()) <= (second.seconds(), second.nanos()));
    assert!(resolution.seconds() > 0 || resolution.nanos() > 0);
    assert!(clock_getres(i32::MAX).unwrap_err().is_errno(EINVAL));
    assert!(Timespec::new(0, 1_000_000_000).is_err());
    assert!(nanosleep(Timespec::new(-1, 0).unwrap())
        .unwrap_err()
        .is_errno(EINVAL));
    assert_eq!(
        nanosleep(Timespec::default()).unwrap(),
        SleepOutcome::Completed
    );
}

#[test]
fn one_shot_timer_becomes_readable_and_reports_one_expiration() {
    let timer = timerfd_create(CLOCK_MONOTONIC, O_NONBLOCK).unwrap();
    assert_eq!(fcntl_getfd(timer.as_fd()).unwrap() & 1, 0);
    let marked_timer = timerfd_create(CLOCK_MONOTONIC, O_CLOEXEC).unwrap();
    assert_eq!(fcntl_getfd(marked_timer.as_fd()).unwrap() & 1, 1);
    close(marked_timer).unwrap();
    assert_eq!(
        timerfd_gettime(timer.as_fd()).unwrap(),
        TimerSpec::default()
    );
    let mut byte_count = [0_u8; 8];
    assert!(read(timer.as_fd(), &mut byte_count)
        .unwrap_err()
        .is_errno(EAGAIN));
    let specification = TimerSpec {
        initial: Timespec::new(0, 1_000_000).unwrap(),
        interval: Timespec::default(),
    };
    assert_eq!(
        timerfd_settime(timer.as_fd(), 0, specification).unwrap(),
        TimerSpec::default()
    );
    let mut entry = [PollEntry::new(timer.as_fd(), POLLIN)];
    assert_eq!(poll(&mut entry, 2_000).unwrap(), 1);
    assert_eq!(entry[0].returned() & POLLIN, POLLIN);
    assert_eq!(
        read(timer.as_fd(), &mut byte_count).unwrap(),
        ReadOutcome::Progress(8)
    );
    assert_eq!(u64::from_ne_bytes(byte_count), 1);
    assert_eq!(
        timerfd_gettime(timer.as_fd()).unwrap(),
        TimerSpec::default()
    );
    assert!(timerfd_settime(timer.as_fd(), i32::MAX, specification)
        .unwrap_err()
        .is_errno(EINVAL));
    assert!(timerfd_create(i32::MAX, 0).unwrap_err().is_errno(EINVAL));
    close(timer).unwrap();
}

#[test]
fn eventfd_nonblocking_semaphore_and_epoll_status_preserve_io_boundaries() {
    const EEXIST: i32 = 17;
    let first = eventfd2(0, EFD_SEMAPHORE | O_NONBLOCK).unwrap();
    let second = eventfd2(1, O_NONBLOCK).unwrap();
    let epoll = epoll_create1(0).unwrap();
    assert_eq!(fcntl_getfd(first.as_fd()).unwrap() & 1, 0);
    let marked_event = eventfd2(0, O_CLOEXEC).unwrap();
    assert_eq!(fcntl_getfd(marked_event.as_fd()).unwrap() & 1, 1);
    close(marked_event).unwrap();
    assert_eq!(fcntl_getfd(epoll.as_fd()).unwrap() & 1, 0);
    let marked_epoll = epoll_create1(O_CLOEXEC).unwrap();
    assert_eq!(fcntl_getfd(marked_epoll.as_fd()).unwrap() & 1, 1);
    close(marked_epoll).unwrap();
    let first_event = EpollEvent {
        events: EPOLLIN,
        data: 0x0102_0304_0506_0708,
    };
    let second_event = EpollEvent {
        events: EPOLLIN,
        data: 0x1122_3344_5566_7788,
    };
    let untouched = EpollEvent {
        events: 0x1234_5678,
        data: 0x9abc_def0_1234_5678,
    };
    let mut events = [untouched; 3];
    assert_eq!(epoll_wait(epoll.as_fd(), &mut events, 0).unwrap(), 0);
    assert_eq!(events, [untouched; 3]);
    assert!(matches!(
        epoll_wait(epoll.as_fd(), &mut [], 0),
        Err(SyscallError::InvalidInput(_))
    ));
    assert!(epoll_wait(first.as_fd(), &mut events, 0)
        .unwrap_err()
        .is_errno(EINVAL));
    assert_eq!(events, [untouched; 3]);

    epoll_ctl(epoll.as_fd(), first.as_fd(), EpollControl::Add(first_event)).unwrap();
    epoll_ctl(
        epoll.as_fd(),
        second.as_fd(),
        EpollControl::Add(second_event),
    )
    .unwrap();
    assert!(
        epoll_ctl(epoll.as_fd(), first.as_fd(), EpollControl::Add(first_event))
            .unwrap_err()
            .is_errno(EEXIST)
    );
    assert_eq!(write(first.as_fd(), &2_u64.to_ne_bytes()).unwrap(), 8);
    assert_eq!(epoll_wait(epoll.as_fd(), &mut events, 2_000).unwrap(), 2);
    events[..2].sort_by_key(|event| event.data);
    assert_eq!(events, [first_event, second_event, untouched]);
    let changed = EpollEvent {
        events: EPOLLIN,
        data: 0x4433_2211,
    };
    epoll_ctl(epoll.as_fd(), first.as_fd(), EpollControl::Modify(changed)).unwrap();
    epoll_ctl(epoll.as_fd(), second.as_fd(), EpollControl::Delete).unwrap();
    assert_eq!(epoll_wait(epoll.as_fd(), &mut events, 0).unwrap(), 1);
    assert_eq!(events, [changed, second_event, untouched]);

    let mut count = [0_u8; 8];
    for _ in 0..2 {
        assert_eq!(
            read(first.as_fd(), &mut count).unwrap(),
            ReadOutcome::Progress(8)
        );
        assert_eq!(u64::from_ne_bytes(count), 1);
    }
    assert!(read(first.as_fd(), &mut count)
        .unwrap_err()
        .is_errno(EAGAIN));
    assert_eq!(epoll_wait(epoll.as_fd(), &mut events, 0).unwrap(), 0);
    close(second).unwrap();
    close(first).unwrap();
    close(epoll).unwrap();
}

#[test]
fn interrupted_sleep_exposes_remaining_duration_without_retrying() {
    const SIGUSR1: i32 = 10;
    extern "C" {
        fn signal(number: i32, handler: usize) -> usize;
        fn pthread_kill(thread: c_ulong, signal: i32) -> i32;
    }
    extern "C" fn handler(_: i32) {}

    let previous = unsafe { signal(SIGUSR1, handler as *const () as usize) };
    assert_ne!(previous, usize::MAX);
    let (ready_tx, ready_rx) = mpsc::channel();
    let (done_tx, done_rx) = mpsc::channel();
    let sleeper = thread::spawn(move || {
        ready_tx.send(()).unwrap();
        let result = nanosleep(Timespec::new(2, 0).unwrap());
        done_tx.send(result).unwrap();
    });
    let pthread = sleeper.as_pthread_t();
    ready_rx.recv().unwrap();
    let mut result = None;
    for _ in 0..100 {
        if let Ok(outcome) = done_rx.recv_timeout(Duration::from_millis(10)) {
            result = Some(outcome);
            break;
        }
        unsafe { pthread_kill(pthread, SIGUSR1) };
    }
    sleeper.join().unwrap();
    unsafe { signal(SIGUSR1, previous) };
    let SleepOutcome::Interrupted { remaining } =
        result.expect("sleep did not terminate early").unwrap()
    else {
        panic!("sleep did not expose its interruption");
    };
    assert!((remaining.seconds(), remaining.nanos()) > (0, 0));
}
