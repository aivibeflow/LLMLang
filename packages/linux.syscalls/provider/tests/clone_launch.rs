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

fn check_launch(
    launch: fn(&ExecImage<'_>) -> Result<ChildPid, SyscallError>,
    policy_denial_allowed: bool,
) {
    let root = std::env::temp_dir().join(format!(
        "llmlang-clone-{}-{}",
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
    let mut variable = b"LLMLANG_CLONE_OUT=".to_vec();
    variable.extend_from_slice(output.as_os_str().as_bytes());
    let destination = CString::new(variable).unwrap();
    let image = ExecImage::new(
        c"/bin/sh",
        &[
            c"sh",
            c"-c",
            c"printf '%s:%s\n' \"$1\" \"$LLMLANG_CLONE_ENV\" > \"$LLMLANG_CLONE_OUT\"; exit 41",
            c"marker",
            c"clone-arg",
        ],
        &[destination.as_c_str(), c"LLMLANG_CLONE_ENV=clone-env"],
    )
    .unwrap();
    let mut child = match launch(&image) {
        Ok(child) => child,
        Err(error) if policy_denial_allowed && (error.is_errno(ENOSYS) || error.is_errno(1)) => {
            assert!(!output.exists());
            eprintln!("clone3 host availability: {error:?}");
            return;
        }
        Err(error) => panic!("launch failed: {error:?}"),
    };
    assert!(child.pid().unwrap() > 0);
    assert_eq!(exit_code(&mut child), 41);
    assert!(child.pid().is_none());
    assert_eq!(std::fs::read(&output).unwrap(), b"clone-arg:clone-env\n");

    let missing = CString::new(scratch.0.join("no-executable").as_os_str().as_bytes()).unwrap();
    let fail_image = ExecImage::new(&missing, &[c"missing"], &[]).unwrap();
    let mut failed_child = launch(&fail_image).unwrap();
    assert_eq!(exit_code(&mut failed_child), 127);
    assert!(failed_child.pid().is_none());
}

#[test]
fn clone_launch_preserves_exec_and_child_status() {
    check_launch(clone_execve, false);
}

#[test]
fn clone3_launch_preserves_exec_status_or_kernel_unavailability() {
    check_launch(clone3_execve, true);
}
