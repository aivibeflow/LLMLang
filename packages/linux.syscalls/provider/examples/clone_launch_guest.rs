use linux_syscalls_provider::*;

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

fn main() -> Result<(), SyscallError> {
    let mut arguments = std::env::args().skip(1);
    match arguments.next().as_deref() {
        Some("--llmlang-clone-child") => {
            let tag = arguments.next().expect("missing child marker");
            assert!(arguments.next().is_none());
            assert_eq!(std::env::var("LLMLANG_CLONE_ENV").unwrap(), "fixed-value");
            println!("LLMLANG_GUEST_CASE {tag}");
            std::process::exit(41);
        }
        Some("--llmlang-disposable-guest-probe") => {
            assert!(arguments.next().is_none());
            assert_eq!(getppid()?, 1, "run through the disposable guest init");
        }
        _ => panic!("expected the disposable guest init"),
    }

    type Launch = fn(&ExecImage<'_>) -> Result<ChildPid, SyscallError>;
    let launches: [(Launch, &std::ffi::CStr); 2] = [
        (clone_execve, c"clone_guest_runs_exec_with_exact_arguments"),
        (
            clone3_execve,
            c"clone3_guest_runs_exec_with_exact_arguments",
        ),
    ];
    for (launch, tag) in launches {
        let image = ExecImage::new(
            c"/probe",
            &[c"probe", c"--llmlang-clone-child", tag],
            &[c"LLMLANG_CLONE_ENV=fixed-value"],
        )?;
        let mut child = launch(&image)?;
        assert!(child.pid().is_some());
        assert_eq!(exit_code(&mut child), 41);
        assert!(child.pid().is_none());

        let image = ExecImage::new(c"/missing", &[c"missing"], &[])?;
        let mut child = launch(&image)?;
        assert_eq!(exit_code(&mut child), 127);
        assert!(child.pid().is_none());
    }
    Ok(())
}
