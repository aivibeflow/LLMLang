use std::sync::mpsc;
use std::thread;
use std::time::{Duration, Instant};

use linux_syscalls_provider::{
    clock_gettime, futex_requeue, futex_wait, futex_wait_private, futex_waitv, futex_wake,
    futex_wake_private, get_robust_list, FutexWaiter, FutexWord, RobustListInfo, SyscallError,
    Timespec, CLOCK_MONOTONIC, EAGAIN,
};

const ETIMEDOUT: i32 = 110;

fn monotonic_deadline(seconds: i64) -> Timespec {
    let now = clock_gettime(CLOCK_MONOTONIC).unwrap();
    Timespec::new(now.seconds() + seconds, now.nanos()).unwrap()
}

#[test]
fn private_futex_waits_report_mismatch_and_their_native_timeout_forms() {
    let word = FutexWord::new(7);
    assert!(futex_wait_private(&word, 8, None)
        .unwrap_err()
        .is_errno(EAGAIN));
    assert!(futex_wait(&word, 8, None).unwrap_err().is_errno(EAGAIN));
    assert!(
        futex_wait_private(&word, 7, Some(Timespec::new(0, 10_000_000).unwrap()))
            .unwrap_err()
            .is_errno(ETIMEDOUT)
    );
    let expired = Timespec::new(0, 0).unwrap();
    assert!(futex_wait(&word, 7, Some(expired))
        .unwrap_err()
        .is_errno(ETIMEDOUT));

    let invalid = Timespec::new(-1, 1).unwrap();
    assert!(matches!(
        futex_wait_private(&word, 7, Some(invalid)),
        Err(SyscallError::InvalidInput(_))
    ));
    assert!(matches!(
        futex_wait(&word, 7, Some(invalid)),
        Err(SyscallError::InvalidInput(_))
    ));
    assert_eq!(word.load(), 7);
}

type Wait = fn(&FutexWord, u32, Option<Timespec>) -> Result<(), SyscallError>;
type Wake = fn(&FutexWord, u32) -> Result<u32, SyscallError>;

fn exercise_wait_and_wake(wait: Wait, wake: Wake, timeout: Timespec) {
    let word = FutexWord::new(7);
    assert_eq!(wake(&word, 1).unwrap(), 0);
    assert!(matches!(wake(&word, 0), Err(SyscallError::InvalidInput(_))));
    assert!(matches!(
        wake(&word, u32::MAX),
        Err(SyscallError::InvalidInput(_))
    ));

    thread::scope(|scope| {
        let (started, entered) = mpsc::sync_channel(0);
        let word = &word;
        let waiter = scope.spawn(move || {
            started.send(()).unwrap();
            wait(word, 7, Some(timeout))
        });
        entered.recv().unwrap();
        let deadline = Instant::now() + Duration::from_secs(1);
        loop {
            if wake(word, 1).unwrap() == 1 {
                break;
            }
            assert!(
                Instant::now() < deadline,
                "waiter did not enter the kernel queue"
            );
            thread::sleep(Duration::from_millis(1));
        }
        assert_eq!(waiter.join().unwrap(), Ok(()));
    });

    assert_eq!(word.load(), 7);
    word.store(9);
    assert!(wait(&word, 7, None).unwrap_err().is_errno(EAGAIN));
}

#[test]
fn private_futex_wakes_are_counted_without_modifying_the_word() {
    exercise_wait_and_wake(
        futex_wait_private,
        futex_wake_private,
        Timespec::new(2, 0).unwrap(),
    );
    exercise_wait_and_wake(futex_wait, futex_wake, monotonic_deadline(2));
}

#[test]
fn private_futex_vector_validates_shape_and_reports_mismatch_and_timeout() {
    let left = FutexWord::new(7);
    let right = FutexWord::new(u32::MAX);
    let waiter = FutexWaiter::new(&left, 7);
    assert!(matches!(
        futex_waitv(&[], None),
        Err(SyscallError::InvalidInput(_))
    ));
    assert!(matches!(
        futex_waitv(&[waiter; 129], None),
        Err(SyscallError::InvalidInput(_))
    ));
    assert!(matches!(
        futex_waitv(&[waiter], Some(Timespec::new(-1, 0).unwrap())),
        Err(SyscallError::InvalidInput(_))
    ));

    assert!(futex_waitv(&[waiter, FutexWaiter::new(&right, 0)], None)
        .unwrap_err()
        .is_errno(EAGAIN));
    assert_eq!(futex_wake(&left, 1).unwrap(), 0);
    assert!(futex_waitv(
        &[waiter, FutexWaiter::new(&right, u32::MAX)],
        Some(Timespec::new(0, 0).unwrap())
    )
    .unwrap_err()
    .is_errno(ETIMEDOUT));
}

#[test]
fn private_futex_vector_returns_the_woken_index() {
    let left = FutexWord::new(7);
    let right = FutexWord::new(8);
    let deadline = monotonic_deadline(4);
    thread::scope(|scope| {
        let (started, entered) = mpsc::sync_channel(0);
        let (left, right) = (&left, &right);
        let waiter = scope.spawn(move || {
            started.send(()).unwrap();
            futex_waitv(
                &[FutexWaiter::new(left, 7), FutexWaiter::new(right, 8)],
                Some(deadline),
            )
        });
        entered.recv().unwrap();
        let watchdog = Instant::now() + Duration::from_secs(2);
        loop {
            if futex_wake(right, 1).unwrap() == 1 {
                break;
            }
            assert!(
                Instant::now() < watchdog,
                "vector did not enter the kernel queue"
            );
            thread::sleep(Duration::from_millis(1));
        }
        assert_eq!(waiter.join().unwrap(), Ok(1));
    });
    assert_eq!(left.load(), 7);
    assert_eq!(right.load(), 8);
    assert_eq!(futex_wake(&left, 1).unwrap(), 0);
}

#[test]
fn private_futex_requeue_compares_and_moves_without_waking_or_writing() {
    let source = FutexWord::new(u32::MAX);
    let destination = FutexWord::new(21);
    for (src, dst, wake, requeue) in [
        (&source, &source, 0, 1),
        (&source, &destination, u32::MAX, 1),
        (&source, &destination, i32::MAX as u32, 1),
    ] {
        assert!(matches!(
            futex_requeue(src, dst, u32::MAX, wake, requeue),
            Err(SyscallError::InvalidInput(_))
        ));
    }
    assert!(futex_requeue(&source, &destination, 0, 0, 1)
        .unwrap_err()
        .is_errno(EAGAIN));
    assert_eq!(
        futex_requeue(&source, &destination, u32::MAX, 0, 0).unwrap(),
        0
    );

    thread::scope(|scope| {
        let (started, entered) = mpsc::sync_channel(0);
        let source = &source;
        let deadline = monotonic_deadline(4);
        let waiter = scope.spawn(move || {
            started.send(()).unwrap();
            futex_wait(source, u32::MAX, Some(deadline))
        });
        entered.recv().unwrap();
        let watchdog = Instant::now() + Duration::from_secs(2);
        loop {
            assert!(futex_requeue(source, &destination, 0, 1, 1)
                .unwrap_err()
                .is_errno(EAGAIN));
            let count = futex_requeue(source, &destination, u32::MAX, 0, 1).unwrap();
            if count == 1 {
                break;
            }
            assert!(
                Instant::now() < watchdog,
                "waiter did not reach source queue"
            );
            thread::sleep(Duration::from_millis(1));
        }
        assert_eq!(futex_wake(source, 1).unwrap(), 0);
        assert_eq!(futex_wake(&destination, 1).unwrap(), 1);
        assert_eq!(waiter.join().unwrap(), Ok(()));
    });

    assert_eq!(source.load(), u32::MAX);
    assert_eq!(destination.load(), 21);
}

#[test]
fn private_futex_requeue_counts_woken_and_moved_waiters() {
    let source = FutexWord::new(4);
    let destination = FutexWord::new(5);
    thread::scope(|scope| {
        let (started, entered) = mpsc::sync_channel(0);
        let source = &source;
        let mut workers = Vec::new();
        let deadline = monotonic_deadline(4);
        for _ in 0..2 {
            let started = started.clone();
            workers.push(scope.spawn(move || {
                started.send(()).unwrap();
                futex_wait(source, 4, Some(deadline))
            }));
        }
        entered.recv().unwrap();
        entered.recv().unwrap();
        let watchdog = Instant::now() + Duration::from_secs(2);
        let mut affected = 0;
        while affected < 2 {
            // The kernel wakes first. If one thread arrived early, move
            // the later waiter without waking it on the next attempt.
            let wake = u32::from(affected == 0);
            affected += futex_requeue(source, &destination, 4, wake, 1).unwrap();
            assert!(
                Instant::now() < watchdog,
                "both waiters did not reach source queue"
            );
            if affected < 2 {
                thread::sleep(Duration::from_millis(1));
            }
        }
        assert_eq!(affected, 2);
        assert_eq!(futex_wake(source, 2).unwrap(), 0);
        assert_eq!(futex_wake(&destination, 2).unwrap(), 1);
        for worker in workers {
            assert_eq!(worker.join().unwrap(), Ok(()));
        }
    });
}

#[test]
fn robust_list_query_projects_only_the_current_threads_presence_and_length() {
    unsafe extern "C" {
        fn syscall(number: std::ffi::c_long, ...) -> std::ffi::c_long;
    }

    fn observation() {
        let mut address: usize = 0;
        let mut head_bytes: usize = 0;
        // Independently observe the same two slots using libc's native entry.
        let result = unsafe {
            syscall(
                274,
                0 as std::ffi::c_long,
                &mut address as *mut usize,
                &mut head_bytes as *mut usize,
            )
        };
        assert_eq!(result, 0);
        assert_eq!(head_bytes, 24);
        assert_eq!(
            get_robust_list().unwrap(),
            RobustListInfo {
                registered: address != 0,
                head_bytes
            },
        );
    }

    observation();
    thread::spawn(observation).join().unwrap();
}

#[test]
fn robust_list_registration_runs_on_an_isolated_worker() {
    use linux_syscalls_provider::set_robust_list;
    if std::env::var_os("LLMLANG_ROBUST_SCOPE_TEST_CHILD").is_none() {
        let output = std::process::Command::new(std::env::current_exe().unwrap())
            .args([
                "--exact",
                "robust_list_registration_runs_on_an_isolated_worker",
            ])
            .env("LLMLANG_ROBUST_SCOPE_TEST_CHILD", "1")
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "robust-list child failed: {}\n{}",
            String::from_utf8_lossy(&output.stdout),
            String::from_utf8_lossy(&output.stderr)
        );
        return;
    }
    let initial = get_robust_list().unwrap();
    assert_eq!(
        set_robust_list().unwrap(),
        RobustListInfo {
            registered: true,
            head_bytes: 24
        }
    );
    assert_eq!(get_robust_list().unwrap(), initial);
}
