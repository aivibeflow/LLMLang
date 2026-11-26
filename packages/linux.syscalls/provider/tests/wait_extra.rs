use linux_syscalls_provider::*;
use std::os::fd::AsFd;
use std::os::raw::c_ulong;
use std::os::unix::thread::JoinHandleExt;
use std::sync::mpsc;
use std::thread;
use std::time::{Duration, Instant};

#[test]
fn legacy_pipe_eventfd_and_epoll_preserve_native_flags() {
    let (reader, writer) = pipe().unwrap();
    let event = eventfd(7).unwrap();
    let poller = epoll_create(1).unwrap();
    assert!(epoll_create(0).unwrap_err().is_errno(EINVAL));
    for descriptor in [&reader, &writer, &event, &poller] {
        assert_eq!(fcntl_getfd(descriptor.as_fd()).unwrap() & 1, 0);
        assert_eq!(fcntl_getfl(descriptor.as_fd()).unwrap() & O_NONBLOCK, 0);
    }

    assert_eq!(write(writer.as_fd(), b"p").unwrap(), 1);
    let mut byte = [0_u8];
    assert_eq!(
        read(reader.as_fd(), &mut byte).unwrap(),
        ReadOutcome::Progress(1)
    );
    assert_eq!(&byte, b"p");
    close(writer).unwrap();
    assert_eq!(read(reader.as_fd(), &mut byte).unwrap(), ReadOutcome::Eof);

    epoll_ctl(
        poller.as_fd(),
        event.as_fd(),
        EpollControl::Add(EpollEvent {
            events: EPOLLIN,
            data: 7,
        }),
    )
    .unwrap();
    let mut events = [EpollEvent::default()];
    assert_eq!(epoll_wait(poller.as_fd(), &mut events, 0).unwrap(), 1);
    assert_eq!(
        events[0],
        EpollEvent {
            events: EPOLLIN,
            data: 7
        }
    );
    let mut count = [0_u8; 8];
    assert_eq!(
        read(event.as_fd(), &mut count).unwrap(),
        ReadOutcome::Progress(8)
    );
    assert_eq!(u64::from_ne_bytes(count), 7);
    assert_eq!(epoll_wait(poller.as_fd(), &mut events, 0).unwrap(), 0);
    close(poller).unwrap();
    close(event).unwrap();
    close(reader).unwrap();
}

#[test]
fn wall_clock_observations_share_linux_epoch() {
    let start = Instant::now();
    let seconds = time().unwrap();
    let time = gettimeofday().unwrap();
    let clock = clock_gettime(CLOCK_REALTIME).unwrap();
    assert!((0..1_000_000).contains(&time.micros()));
    // Allow rollover, as well as scheduler delays between the observations.
    let distance = start.elapsed().as_secs() + 1;
    assert!(seconds.abs_diff(time.seconds()) <= distance);
    assert!(time.seconds().abs_diff(clock.seconds()) <= distance);
}

#[test]
fn clock_sleep_keeps_relative_and_absolute_modes_distinct() {
    let zero = Timespec::default();
    for mode in [ClockSleepMode::Relative, ClockSleepMode::Absolute] {
        assert_eq!(
            clock_nanosleep(CLOCK_MONOTONIC, mode, zero).unwrap(),
            ClockSleepOutcome::Completed
        );
        assert!(clock_nanosleep(i32::MAX, mode, zero)
            .unwrap_err()
            .is_errno(EINVAL));
        let negative = Timespec::new(-1, 0).unwrap();
        assert!(clock_nanosleep(CLOCK_MONOTONIC, mode, negative)
            .unwrap_err()
            .is_errno(EINVAL));
    }
}

#[test]
fn clock_sleep_interrupts_return_only_relative_remainder() {
    const SIGUSR1: i32 = 10;
    extern "C" {
        fn signal(number: i32, handler: usize) -> usize;
        fn pthread_kill(thread: c_ulong, signal: i32) -> i32;
    }
    extern "C" fn handler(_: i32) {}

    let previous = unsafe { signal(SIGUSR1, handler as *const () as usize) };
    assert_ne!(previous, usize::MAX);
    let mut observations = Vec::new();
    for mode in [ClockSleepMode::Relative, ClockSleepMode::Absolute] {
        let (ready_send, ready_receive) = mpsc::channel();
        let (done_send, done_receive) = mpsc::channel();
        let sleeper = thread::spawn(move || {
            let request = match mode {
                ClockSleepMode::Relative => Timespec::new(2, 0).unwrap(),
                ClockSleepMode::Absolute => {
                    let now = clock_gettime(CLOCK_MONOTONIC).unwrap();
                    Timespec::new(now.seconds() + 2, now.nanos()).unwrap()
                }
            };
            ready_send.send(()).unwrap();
            let result = clock_nanosleep(CLOCK_MONOTONIC, mode, request);
            done_send.send(result).unwrap();
        });
        ready_receive.recv().unwrap();
        let pthread = sleeper.as_pthread_t();
        let mut outcome = None;
        for _ in 0..100 {
            if let Ok(result) = done_receive.recv_timeout(Duration::from_millis(10)) {
                outcome = Some(result);
                break;
            }
            // The joinable thread identity remains valid until join.
            unsafe { pthread_kill(pthread, SIGUSR1) };
        }
        sleeper.join().unwrap();
        observations.push(outcome);
    }
    unsafe { signal(SIGUSR1, previous) };
    let ClockSleepOutcome::Interrupted {
        remaining: Some(remaining),
    } = observations[0]
        .expect("relative sleep did not return early")
        .unwrap()
    else {
        panic!("relative interruption needs the remaining duration");
    };
    assert!((remaining.seconds(), remaining.nanos()) > (0, 0));
    assert_eq!(
        observations[1]
            .expect("absolute sleep did not return early")
            .unwrap(),
        ClockSleepOutcome::Interrupted { remaining: None }
    );
}

#[test]
fn ppoll_honors_timeout_and_preserves_returned_events_on_error() {
    let (reader, writer) = pipe2(O_NONBLOCK).unwrap();
    let mut entries = [PollEntry::new(reader.as_fd(), POLLIN)];
    let immediate = Some(Timespec::default());
    assert_eq!(ppoll(&mut entries, immediate).unwrap(), 0);
    assert_eq!(entries[0].returned(), 0);
    let timeout = Some(Timespec::new(0, 1_000_000).unwrap());
    assert_eq!(ppoll(&mut entries, timeout).unwrap(), 0);
    assert_eq!(write(writer.as_fd(), b"x").unwrap(), 1);
    assert_eq!(ppoll(&mut entries, immediate).unwrap(), 1);
    let ready = entries[0].returned();
    assert_eq!(ready & POLLIN, POLLIN);
    let negative = Some(Timespec::new(-1, 0).unwrap());
    assert!(ppoll(&mut entries, negative).unwrap_err().is_errno(EINVAL));
    assert_eq!(entries[0].returned(), ready);
    assert_eq!(ppoll(&mut [], immediate).unwrap(), 0);
    close(writer).unwrap();
    close(reader).unwrap();
}
