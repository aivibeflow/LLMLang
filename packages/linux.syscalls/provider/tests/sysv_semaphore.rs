use linux_syscalls_provider::*;

const ERANGE: i32 = 34;

fn operation(index: u16, delta: i16, mode: SemaphoreMode) -> SemaphoreOperation {
    SemaphoreOperation { index, delta, mode }
}

#[test]
fn semaphore_operations_are_atomic_and_observe_values() {
    let set = semget(2, 0o600).unwrap();
    assert_eq!(set.count(), 2);
    assert_eq!(semctl_getval(&set, 0).unwrap(), 0);
    assert_eq!(semctl_getval(&set, 1).unwrap(), 0);
    let no_wait = SemaphoreMode::NoWait;
    let blocked = [operation(0, 2, no_wait), operation(1, -1, no_wait)];
    assert!(semop(&set, &blocked).unwrap_err().is_errno(EAGAIN));
    assert_eq!(semctl_getval(&set, 0).unwrap(), 0);
    assert_eq!(semctl_getval(&set, 1).unwrap(), 0);

    semctl_setval(&set, 1, 1).unwrap();
    semop(&set, &blocked).unwrap();
    assert_eq!(semctl_getval(&set, 0).unwrap(), 2);
    assert_eq!(semctl_getval(&set, 1).unwrap(), 0);
    let zero_wait = [operation(0, -2, no_wait), operation(0, 0, no_wait)];
    semop(&set, &zero_wait).unwrap();
    assert_eq!(semctl_getval(&set, 0).unwrap(), 0);

    let independent = semget(2, 0o600).unwrap();
    semctl_setval(&independent, 0, 7).unwrap();
    assert_eq!(semctl_getval(&set, 0).unwrap(), 0);
    semctl_remove(independent).unwrap();
    semctl_remove(set).unwrap();
}

#[test]
fn semaphore_timed_waits_and_validation_preserve_state() {
    assert!(matches!(
        semget(0, 0o600),
        Err(SyscallError::InvalidInput(_))
    ));
    assert!(matches!(
        semget(u32::MAX, 0o600),
        Err(SyscallError::InvalidInput(_))
    ));
    assert!(matches!(
        semget(1, 0o1600),
        Err(SyscallError::InvalidInput(_))
    ));
    let set = semget(1, 0o600).unwrap();
    let wait = SemaphoreMode::Wait;
    assert!(matches!(
        semop(&set, &[]),
        Err(SyscallError::InvalidInput(_))
    ));
    assert!(matches!(
        semop(&set, &[operation(1, 1, wait)]),
        Err(SyscallError::InvalidInput(_))
    ));
    assert!(matches!(
        semctl_getval(&set, 1),
        Err(SyscallError::InvalidInput(_))
    ));
    assert!(matches!(
        semctl_setval(&set, 1, 3),
        Err(SyscallError::InvalidInput(_))
    ));
    let decrement = [operation(0, -1, wait)];
    assert!(semtimedop(&set, &decrement, Some(Timespec::default()))
        .unwrap_err()
        .is_errno(EAGAIN));
    assert!(
        semtimedop(&set, &decrement, Some(Timespec::new(0, 1_000_000).unwrap()))
            .unwrap_err()
            .is_errno(EAGAIN)
    );
    assert!(
        semtimedop(&set, &decrement, Some(Timespec::new(-1, 0).unwrap()))
            .unwrap_err()
            .is_errno(EINVAL)
    );
    assert_eq!(semctl_getval(&set, 0).unwrap(), 0);
    assert!(semctl_setval(&set, 0, u16::MAX)
        .unwrap_err()
        .is_errno(ERANGE));
    assert_eq!(semctl_getval(&set, 0).unwrap(), 0);
    semctl_setval(&set, 0, 32_767).unwrap();
    assert!(semop(&set, &[operation(0, 1, wait)])
        .unwrap_err()
        .is_errno(ERANGE));
    assert_eq!(semctl_getval(&set, 0).unwrap(), 32_767);
    semtimedop(&set, &decrement, None).unwrap();
    assert_eq!(semctl_getval(&set, 0).unwrap(), 32_766);
}

#[test]
fn semaphore_waits_return_eintr_without_applying_operations() {
    use std::ffi::c_ulong;
    use std::process::Command;
    use std::sync::mpsc;
    use std::time::Duration;

    const TEST: &str = "semaphore_waits_return_eintr_without_applying_operations";
    const CHILD: &str = "LLMLANG_SYSV_SEMAPHORE_SIGNAL_CHILD";
    if std::env::var_os(CHILD).is_none() {
        let output = Command::new(std::env::current_exe().unwrap())
            .args(["--exact", TEST, "--nocapture"])
            .env(CHILD, "1")
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "{} {}",
            String::from_utf8_lossy(&output.stdout),
            String::from_utf8_lossy(&output.stderr)
        );
        return;
    }

    const SIGUSR1: i32 = 10;
    unsafe extern "C" {
        fn signal(number: i32, handler: usize) -> usize;
        fn pthread_kill(thread: c_ulong, number: i32) -> i32;
        fn pthread_self() -> c_ulong;
    }
    extern "C" fn handler(_: i32) {}
    assert_ne!(
        unsafe { signal(SIGUSR1, handler as *const () as usize) },
        usize::MAX
    );

    for timed in [false, true] {
        let set = semget(2, 0o600).unwrap();
        let interrupted = std::thread::scope(|scope| {
            let (started, ready) = mpsc::channel();
            let (done, result) = mpsc::channel();
            let borrowed = &set;
            let worker = scope.spawn(move || {
                let operations = [
                    operation(0, 1, SemaphoreMode::Wait),
                    operation(1, -1, SemaphoreMode::Wait),
                ];
                started.send(unsafe { pthread_self() }).unwrap();
                let received = if timed {
                    semtimedop(borrowed, &operations, Some(Timespec::new(2, 0).unwrap()))
                } else {
                    semop(borrowed, &operations)
                };
                done.send(received).unwrap();
            });
            let pthread = ready.recv().unwrap();
            let mut observed = None;
            for _ in 0..100 {
                let delivered = unsafe { pthread_kill(pthread, SIGUSR1) };
                if delivered != 0 && !(delivered == 3 && worker.is_finished()) {
                    break;
                }
                if let Ok(outcome) = result.recv_timeout(Duration::from_millis(5)) {
                    observed = Some(outcome);
                    break;
                }
            }
            if observed.is_none() {
                // Release a regressed implementation that inadvertently retries EINTR.
                semctl_setval(&set, 1, 1).unwrap();
            }
            worker.join().unwrap();
            observed
        });
        assert!(interrupted
            .expect("blocked semaphore wait did not return after signal")
            .unwrap_err()
            .is_errno(EINTR));
        assert_eq!(semctl_getval(&set, 0).unwrap(), 0);
        assert_eq!(semctl_getval(&set, 1).unwrap(), 0);
    }
}
