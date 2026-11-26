use linux_syscalls_provider::*;
use std::ffi::CString;
use std::os::unix::ffi::OsStrExt;

fn exit_code(child: &mut ChildPid) -> u8 {
    loop {
        match wait4(child, 0) {
            Ok(Some(status)) => return status.exited().expect("child must exit normally"),
            Ok(None) => panic!("blocking wait returned no status"),
            Err(error) if error.is_errno(EINTR) => continue,
            Err(error) => panic!("wait failed: {error:?}"),
        }
    }
}

#[test]
fn sealed_execveat_replaces_child_and_preserves_native_failure() {
    let executable = prepare_execveat_fd(&std::fs::read("/bin/sh").unwrap()).unwrap();
    let root = std::env::temp_dir().join(format!(
        "llmlang-execveat-{}-{}",
        std::process::id(),
        gettid().unwrap()
    ));
    std::fs::create_dir(&root).unwrap();
    struct Scratch(std::path::PathBuf);
    impl Drop for Scratch {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.0);
        }
    }
    let scratch = Scratch(root);
    let output = scratch.0.join("output");
    let mut variable = b"LLMLANG_EXECVEAT_OUT=".to_vec();
    variable.extend_from_slice(output.as_os_str().as_bytes());
    let destination = CString::new(variable).unwrap();
    let image = ExecveAtImage::new(
        &executable,
        &[
            c"sh",
            c"-c",
            c"printf '%s:%s\n' \"$1\" \"$LLMLANG_EXECVEAT_ENV\" > \"$LLMLANG_EXECVEAT_OUT\"; exit 46",
            c"marker",
            c"sealed-arg",
        ],
        &[destination.as_c_str(), c"LLMLANG_EXECVEAT_ENV=sealed-env"],
    )
    .unwrap();
    let mut child = fork_execveat(&image).unwrap();
    assert_eq!(exit_code(&mut child), 46);
    assert!(child.pid().is_none());
    assert_eq!(std::fs::read(&output).unwrap(), b"sealed-arg:sealed-env\n");

    let malformed = prepare_execveat_fd(b"not an executable").unwrap();
    let missing = ExecveAtImage::new(&malformed, &[c"malformed"], &[]).unwrap();
    assert!(execveat(&missing).unwrap_err().is_errno(8));
    let mut child = fork_execveat(&missing).unwrap();
    assert_eq!(exit_code(&mut child), 127);
    assert!(child.pid().is_none());
}

fn mask() -> u64 {
    unsafe extern "C" {
        fn syscall(number: i64, ...) -> i64;
    }
    let mut mask = 0_u64;
    assert_eq!(
        unsafe {
            syscall(
                14,
                0_usize,
                0_usize,
                std::ptr::from_mut(&mut mask),
                std::mem::size_of::<u64>(),
            )
        },
        0
    );
    mask
}

#[test]
fn masked_vfork_restores_calling_thread_and_child_status() {
    let outer = mask();
    rt_sigprocmask(UserSignals::USER1, |_| {
        let previous = mask();
        assert_ne!(previous & (1 << 9), 0);
        let program = ExecImage::new(c"/bin/sh", &[c"sh", c"-c", c"exit 41"], &[]).unwrap();
        let mut child = vfork_execve_masked(&program).unwrap();
        assert_eq!(mask(), previous);
        assert_eq!(exit_code(&mut child), 41);
        assert!(child.pid().is_none());

        let invalid = ExecImage::new(c"/dev/null/not-an-executable", &[c"missing"], &[]).unwrap();
        let mut child = vfork_execve_masked(&invalid).unwrap();
        assert_eq!(mask(), previous);
        assert_eq!(exit_code(&mut child), 127);
        assert!(child.pid().is_none());
    })
    .unwrap();
    assert_eq!(mask(), outer);
}
