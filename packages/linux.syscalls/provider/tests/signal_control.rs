use linux_syscalls_provider::{
    fork_execve, getpid, getuid, kill, rt_sigprocmask, signalfd4, signalfd_read, tgkill, tkill,
    wait4, ChildSignal, ExecImage, SyscallError, UserSignal, UserSignals, EAGAIN, EINTR,
};
use std::{env, process::Command};

#[test]
fn kill_checks_and_terminates_only_the_owned_child() {
    let image = ExecImage::new(c"/bin/sleep", &[c"sleep", c"5"], &[]).unwrap();
    let mut child = fork_execve(&image).unwrap();
    let available = kill(&child, ChildSignal::Check);
    let terminate = kill(&child, ChildSignal::Terminate);
    // Reap the bounded fixture even when the kernel denies signaling.
    let status = loop {
        match wait4(&mut child, 0) {
            Err(error) if error.is_errno(EINTR) => continue,
            result => break result.unwrap().unwrap(),
        }
    };
    available.unwrap();
    terminate.unwrap();
    assert_eq!(status.signal(), Some(15));
    assert!(matches!(
        kill(&child, ChildSignal::Check),
        Err(SyscallError::InvalidInput(_))
    ));
}

fn run_in_subprocess(name: &str) -> bool {
    const MARKER: &str = "LLMLANG_SYSCALL_SIGNAL_CONTROL_CHILD";
    if env::var(MARKER).as_deref() == Ok(name) {
        return false;
    }
    let output = Command::new(env::current_exe().unwrap())
        .args(["--exact", name, "--nocapture"])
        .env(MARKER, name)
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "isolated test failed: {}\n{}\n{}",
        output.status,
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    true
}

#[test]
fn thread_signal_calls_route_to_the_blocked_caller() {
    if run_in_subprocess("thread_signal_calls_route_to_the_blocked_caller") {
        return;
    }
    rt_sigprocmask(UserSignals::USER1, |scope| {
        let signal_fd = signalfd4(scope).unwrap();
        for deliver in [tkill, tgkill] {
            assert!(matches!(
                deliver(scope, UserSignal::User2),
                Err(SyscallError::InvalidInput(_))
            ));
            assert!(signalfd_read(&signal_fd).unwrap_err().is_errno(EAGAIN));
            deliver(scope, UserSignal::User1).unwrap();
            let event = signalfd_read(&signal_fd).unwrap();
            assert_eq!(event.signal, UserSignal::User1);
            assert_eq!(event.pid, getpid().unwrap() as u32);
            assert_eq!(event.uid, getuid().unwrap());
            assert_eq!(event.code, -6); // SI_TKILL
        }
        assert!(signalfd_read(&signal_fd).unwrap_err().is_errno(EAGAIN));
        signal_fd.close().unwrap();
    })
    .unwrap();
}

#[repr(C)]
struct FilterInstruction {
    code: u16,
    jump_true: u8,
    jump_false: u8,
    value: u32,
}

#[repr(C)]
struct FilterProgram {
    count: u16,
    filters: *const FilterInstruction,
}

unsafe extern "C" {
    fn prctl(option: i32, ...) -> i32;
}

fn intercept_thread_signals_in_this_test_thread() {
    // An errno oracle, not a sandbox: distinct results reveal which native
    // entry the provider actually called without injecting a pending signal.
    const LOAD_WORD: u16 = 0x20;
    const EQUAL: u16 = 0x15;
    const RESULT: u16 = 0x06;
    const ERRNO: u32 = 0x0005_0000;
    const ALLOW: u32 = 0x7fff_0000;
    const AUDIT_ARCH_X86_64: u32 = 0xc000_003e;
    let instruction = |code, value, jump_false| FilterInstruction {
        code,
        value,
        jump_true: 0,
        jump_false,
    };
    let filters = [
        instruction(LOAD_WORD, 4, 0),
        instruction(EQUAL, AUDIT_ARCH_X86_64, 5),
        instruction(LOAD_WORD, 0, 0),
        instruction(EQUAL, 200, 1), // tkill
        instruction(RESULT, ERRNO | EAGAIN as u32, 0),
        instruction(EQUAL, 234, 1),         // tgkill
        instruction(RESULT, ERRNO | 16, 0), // EBUSY
        instruction(RESULT, ALLOW, 0),
    ];
    let program = FilterProgram {
        count: filters.len() as u16,
        filters: filters.as_ptr(),
    };
    unsafe {
        assert_eq!(prctl(38, 1_usize, 0_usize, 0_usize, 0_usize), 0); // PR_SET_NO_NEW_PRIVS
        assert_eq!(
            prctl(
                22,
                2_usize,
                &program as *const FilterProgram,
                0_usize,
                0_usize
            ),
            0
        ); // PR_SET_SECCOMP, FILTER
    }
}

#[test]
fn thread_signal_entries_preserve_distinct_kernel_errors() {
    if run_in_subprocess("thread_signal_entries_preserve_distinct_kernel_errors") {
        return;
    }
    intercept_thread_signals_in_this_test_thread();
    rt_sigprocmask(UserSignals::USER1, |scope| {
        let signal_fd = signalfd4(scope).unwrap();
        assert!(tkill(scope, UserSignal::User1)
            .unwrap_err()
            .is_errno(EAGAIN));
        assert!(tgkill(scope, UserSignal::User1).unwrap_err().is_errno(16)); // EBUSY
        assert!(signalfd_read(&signal_fd).unwrap_err().is_errno(EAGAIN));
        signal_fd.close().unwrap();
    })
    .unwrap();
}
