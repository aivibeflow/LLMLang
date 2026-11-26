use linux_syscalls_provider::*;
use std::process::Command;

#[test]
fn process_group_and_session_changes_are_child_local() {
    const MODE: &str = "LLMLANG_PROCESS_GROUP_FIXTURE";
    match std::env::var(MODE).as_deref() {
        Ok("group") => {
            setpgid_self().unwrap();
            assert_eq!(getpgrp().unwrap(), getpid().unwrap());
            assert_eq!(getpgid(0).unwrap(), getpgrp().unwrap());
            assert!(setsid().unwrap_err().is_errno(1));
        }
        Ok("session") => {
            assert_ne!(getpgrp().unwrap(), getpid().unwrap());
            assert_eq!(setsid().unwrap(), getpid().unwrap());
            assert_eq!(getsid(0).unwrap(), getpid().unwrap());
            assert_eq!(getpgrp().unwrap(), getpid().unwrap());
            assert!(setpgid_self().unwrap_err().is_errno(1));
        }
        _ => {
            let parent_group = getpgrp().unwrap();
            for requested in ["group", "session"] {
                let output = Command::new(std::env::current_exe().unwrap())
                    .args([
                        "--exact",
                        "process_group_and_session_changes_are_child_local",
                    ])
                    .env(MODE, requested)
                    .output()
                    .unwrap();
                assert!(
                    output.status.success(),
                    "{}",
                    String::from_utf8_lossy(&output.stdout)
                );
            }
            assert_eq!(getpgrp().unwrap(), parent_group);
        }
    }
}

#[test]
fn exit_group_returns_the_kernel_status_without_returning_to_source() {
    const MODE: &str = "LLMLANG_EXIT_GROUP_FIXTURE";
    if std::env::var_os(MODE).is_some() {
        panic!("exit_group returned: {:?}", exit_group(297));
    }
    let output = Command::new(std::env::current_exe().unwrap())
        .args([
            "--exact",
            "exit_group_returns_the_kernel_status_without_returning_to_source",
        ])
        .env(MODE, "1")
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(41));
}

#[test]
fn exit_group_without_clear_tid_preserves_status_and_never_returns() {
    const MODE: &str = "LLMLANG_EXIT_WITHOUT_CLEAR_TID_FIXTURE";
    if std::env::var_os(MODE).is_some() {
        panic!(
            "exit with clear TID disabled returned: {:?}",
            exit_group_without_clear_tid(297)
        );
    }
    let output = Command::new(std::env::current_exe().unwrap())
        .args([
            "--exact",
            "exit_group_without_clear_tid_preserves_status_and_never_returns",
        ])
        .env(MODE, "1")
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(41), "{output:?}");
}

#[test]
fn fork_exit_delivers_exact_child_status_without_running_parent_continuation() {
    for status in [0, 297, -1] {
        let mut child = fork_exit(status).unwrap();
        let outcome = loop {
            match wait4(&mut child, 0) {
                Err(error) if error.is_errno(EINTR) => continue,
                result => break result.unwrap().unwrap(),
            }
        };
        assert_eq!(outcome.exited(), Some((status & 255) as u8));
        assert_eq!(child.pid(), None);
    }
}

#[test]
fn exit_group_without_clear_tid_preserves_denial_of_exact_null_registration() {
    const MODE: &str = "LLMLANG_NULL_CLEAR_TID_DENIAL";
    if std::env::var_os(MODE).is_none() {
        let output = Command::new(std::env::current_exe().unwrap())
            .args([
                "--exact",
                "exit_group_without_clear_tid_preserves_denial_of_exact_null_registration",
            ])
            .env(MODE, "1")
            .output()
            .unwrap();
        assert!(output.status.success(), "{output:?}");
        return;
    }

    #[repr(C)]
    struct Instruction(u16, u8, u8, u32);
    #[repr(C)]
    struct FilterProgram {
        length: u16,
        instructions: *const Instruction,
    }
    extern "C" {
        fn prctl(option: i32, ...) -> i32;
    }

    let instructions = [
        Instruction(0x20, 0, 0, 0),           // Native syscall number.
        Instruction(0x15, 0, 6, 218),         // Leave other calls unchanged.
        Instruction(0x20, 0, 0, 16),          // Low 32 bits of the first argument.
        Instruction(0x15, 0, 3, 0),
        Instruction(0x20, 0, 0, 20),          // High 32 bits of the first argument.
        Instruction(0x15, 0, 1, 0),
        Instruction(0x06, 0, 0, 0x0005_0001), // Null registration is denied with EPERM.
        Instruction(0x06, 0, 0, 0x0005_0016), // Any other pointer is denied with EINVAL.
        Instruction(0x06, 0, 0, 0x7fff_0000),
    ];
    let program = FilterProgram {
        length: instructions.len() as u16,
        instructions: instructions.as_ptr(),
    };
    unsafe {
        assert_eq!(prctl(38, 1_usize, 0_usize, 0_usize, 0_usize), 0);
        assert_eq!(prctl(22, 2_usize, &raw const program, 0_usize, 0_usize), 0);
    }
    assert!(exit_group_without_clear_tid(41).unwrap_err().is_errno(1));
}
