use linux_syscalls_provider::{rt_sigaction, sigaltstack, SignalActionScopeError, UserSignal};

unsafe extern "C" {
    fn signal(number: i32, handler: usize) -> usize;
    fn prctl(option: i32, ...) -> i32;
    fn pthread_self() -> usize;
    fn pthread_sigqueue(thread: usize, signal: i32, value: SignalValue) -> i32;
}

#[repr(C)]
union SignalValue {
    integer: i32,
    bits: u64,
}

fn isolate(name: &str) -> bool {
    const MARKER: &str = "LLMLANG_FIXED_SIGNAL_SCOPE_CHILD";
    if std::env::var(MARKER).as_deref() == Ok(name) {
        return false;
    }
    let output = std::process::Command::new(std::env::current_exe().unwrap())
        .args(["--exact", name])
        .env(MARKER, name)
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "isolated child failed: {}\n{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr),
    );
    true
}

#[test]
fn fixed_signal_action_returns_through_kernel_restorer_without_changing_caller() {
    if isolate("fixed_signal_action_returns_through_kernel_restorer_without_changing_caller") {
        return;
    }
    assert_ne!(unsafe { signal(10, 1) }, usize::MAX); // SIG_IGN inside the disposable fixture.
    rt_sigaction(UserSignal::User1).unwrap();
    rt_sigaction(UserSignal::User2).unwrap();
    assert_eq!(unsafe { signal(10, 1) }, 1);
}

#[test]
fn fixed_signal_action_observes_owned_alternate_stack_and_returns() {
    if isolate("fixed_signal_action_observes_owned_alternate_stack_and_returns") {
        return;
    }
    sigaltstack(UserSignal::User1).unwrap();
    sigaltstack(UserSignal::User2).unwrap();
    rt_sigaction(UserSignal::User1).unwrap();
}

#[test]
fn fixed_signal_action_rolls_back_after_denied_delivery() {
    if isolate("fixed_signal_action_rolls_back_after_denied_delivery") {
        return;
    }
    #[repr(C)]
    struct Filter {
        instruction: u16,
        yes: u8,
        no: u8,
        value: u32,
    }
    #[repr(C)]
    struct Program {
        length: u16,
        instructions: *const Filter,
    }

    let filter = |instruction, value, no| Filter {
        instruction,
        yes: 0,
        no,
        value,
    };
    let filters = [
        filter(0x20, 0, 0),           // Load syscall number.
        filter(0x15, 234, 1),         // Only deny tgkill.
        filter(0x06, 0x0005_0001, 0), // SECCOMP_RET_ERRNO | EPERM.
        filter(0x06, 0x7fff_0000, 0), // SECCOMP_RET_ALLOW.
    ];
    let program = Program {
        length: filters.len() as u16,
        instructions: filters.as_ptr(),
    };

    unsafe {
        assert_ne!(signal(10, 1), usize::MAX);
        assert_eq!(prctl(38, 1_usize, 0_usize, 0_usize, 0_usize), 0);
        assert_eq!(
            prctl(22, 2_usize, &program as *const Program, 0_usize, 0_usize),
            0
        );
    }
    for operation in [
        rt_sigaction,
        sigaltstack,
        linux_syscalls_provider::rt_sigsuspend,
    ] {
        assert!(
            matches!(operation(UserSignal::User1), Err(SignalActionScopeError::Child(error)) if error.is_errno(1))
        );
        assert_eq!(unsafe { signal(10, 1) }, 1);
    }
}

#[test]
fn fixed_signal_waits_return_through_restorer_without_changing_caller() {
    use linux_syscalls_provider::{pause, rt_sigsuspend};

    if isolate("fixed_signal_waits_return_through_restorer_without_changing_caller") {
        return;
    }
    assert_ne!(unsafe { signal(14, 1) }, usize::MAX);
    assert_ne!(unsafe { signal(10, 1) }, usize::MAX);
    pause().unwrap();
    rt_sigsuspend(UserSignal::User1).unwrap();
    rt_sigsuspend(UserSignal::User2).unwrap();
    assert_eq!(unsafe { signal(14, 1) }, 1);
    assert_eq!(unsafe { signal(10, 1) }, 1);
}

#[test]
fn fixed_signal_queue_roundtrips_both_targets_and_signed_values() {
    use linux_syscalls_provider::{rt_sigqueueinfo, rt_tgsigqueueinfo};

    if isolate("fixed_signal_queue_roundtrips_both_targets_and_signed_values") {
        return;
    }
    rt_sigqueueinfo(UserSignal::User1, i32::MIN).unwrap();
    rt_sigqueueinfo(UserSignal::User2, 0).unwrap();
    rt_tgsigqueueinfo(UserSignal::User2, i32::MAX).unwrap();
    rt_tgsigqueueinfo(UserSignal::User1, -42).unwrap();
}

#[test]
fn scoped_signal_wait_checks_relative_timeout_and_exact_self_sender() {
    use linux_syscalls_provider::{
        getpid, getuid, rt_sigprocmask, rt_sigtimedwait, tgkill, SignalWaitEvent, SignalWaitSender,
        SyscallError, Timespec, UserSignals, EAGAIN,
    };

    if isolate("scoped_signal_wait_checks_relative_timeout_and_exact_self_sender") {
        return;
    }
    let timeout = Timespec::new(0, 1_000_000).unwrap();
    rt_sigprocmask(UserSignals::USER2, |scope| {
        for timeout in [Timespec::default(), timeout] {
            assert!(matches!(rt_sigtimedwait(scope, Some(timeout)), Err(error) if error.is_errno(EAGAIN)));
        }
        assert!(matches!(
            rt_sigtimedwait(scope, Some(Timespec::new(-1, 0).unwrap())),
            Err(SyscallError::InvalidInput(_))
        ));
        tgkill(scope, UserSignal::User2).unwrap();
        assert_eq!(
            rt_sigtimedwait(scope, Some(Timespec::default())).unwrap(),
            SignalWaitEvent {
                signal: UserSignal::User2,
                code: -6,
                errno: 0,
                sender: Some(SignalWaitSender {
                    pid: getpid().unwrap(),
                    uid: getuid().unwrap(),
                }),
                queued_value: None,
            }
        );
        let payload = -12_345_i32;
        let value = SignalValue {
            bits: u64::from(payload as u32),
        };
        // The selected signal is blocked here and the libc fixture targets only
        // the current thread, so no other thread can consume or handle it.
        assert_eq!(
            unsafe { pthread_sigqueue(pthread_self(), UserSignal::User2 as i32, value) },
            0
        );
        assert_eq!(
            rt_sigtimedwait(scope, None).unwrap(),
            SignalWaitEvent {
                signal: UserSignal::User2,
                code: -1,
                errno: 0,
                sender: Some(SignalWaitSender {
                    pid: getpid().unwrap(),
                    uid: getuid().unwrap(),
                }),
                queued_value: Some(payload),
            }
        );
        assert!(matches!(rt_sigtimedwait(scope, Some(Timespec::default())), Err(error) if error.is_errno(EAGAIN)));
    })
    .unwrap();
}
