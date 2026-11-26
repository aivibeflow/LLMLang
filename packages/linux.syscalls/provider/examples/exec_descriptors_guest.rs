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

fn read_mask() -> u64 {
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

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let entry_mask = read_mask();
    let mut args = std::env::args().skip(1);
    match args.next().as_deref() {
        Some("--llmlang-vfork-child") => {
            assert_eq!(args.next().as_deref(), Some("vfork-arg"));
            assert!(args.next().is_none());
            assert_eq!(std::env::var("LLMLANG_CHILD_ENV")?, "vfork-env");
            assert_eq!(entry_mask, u64::MAX & !(1 << (9 - 1)) & !(1 << (19 - 1)));
            std::process::exit(41);
        }
        Some("--llmlang-execveat-child") => {
            assert_eq!(args.next().as_deref(), Some("at-arg"));
            assert!(args.next().is_none());
            assert_eq!(std::env::var("LLMLANG_CHILD_ENV")?, "at-env");
            std::process::exit(46);
        }
        Some("--llmlang-direct-execveat") => {
            let executable = prepare_execveat_fd(&std::fs::read("/probe")?)?;
            let image = ExecveAtImage::new(
                &executable,
                &[c"probe", c"--llmlang-execveat-child", c"at-arg"],
                &[c"LLMLANG_CHILD_ENV=at-env"],
            )?;
            match execveat(&image) {
                Ok(never) => match never {},
                Err(error) => return Err(error.into()),
            }
        }
        Some("--llmlang-disposable-guest-probe") => {
            assert!(args.next().is_none());
            assert_eq!(getppid()?, 1, "run through the disposable guest init");
        }
        _ => panic!("expected the disposable guest init"),
    }

    let executable = prepare_execveat_fd(&std::fs::read("/probe")?)?;
    let image = ExecveAtImage::new(
        &executable,
        &[c"probe", c"--llmlang-execveat-child", c"at-arg"],
        &[c"LLMLANG_CHILD_ENV=at-env"],
    )?;
    let mut child = fork_execveat(&image)?;
    assert_eq!(exit_code(&mut child), 46);
    assert!(child.pid().is_none());

    let direct = ExecImage::new(c"/probe", &[c"probe", c"--llmlang-direct-execveat"], &[])?;
    let mut child = fork_execve(&direct)?;
    assert_eq!(exit_code(&mut child), 46);
    assert!(child.pid().is_none());
    println!("LLMLANG_GUEST_CASE execveat_guest_runs_sealed_descriptor_with_exact_arguments");

    let invalid = prepare_execveat_fd(b"not an executable")?;
    let image = ExecveAtImage::new(&invalid, &[c"invalid"], &[])?;
    assert!(execveat(&image).unwrap_err().is_errno(8));
    let mut child = fork_execveat(&image)?;
    assert_eq!(exit_code(&mut child), 127);
    assert!(child.pid().is_none());
    println!("LLMLANG_GUEST_CASE execveat_guest_preserves_invalid_image_error_and_child_fallback");

    let before = read_mask();
    let image = ExecImage::new(
        c"/probe",
        &[c"probe", c"--llmlang-vfork-child", c"vfork-arg"],
        &[c"LLMLANG_CHILD_ENV=vfork-env"],
    )?;
    let mut child = vfork_execve_masked(&image)?;
    assert_eq!(read_mask(), before);
    assert_eq!(exit_code(&mut child), 41);
    assert!(child.pid().is_none());

    let image = ExecImage::new(c"/missing", &[c"missing"], &[])?;
    let mut child = vfork_execve_masked(&image)?;
    assert_eq!(read_mask(), before);
    assert_eq!(exit_code(&mut child), 127);
    assert!(child.pid().is_none());
    println!("LLMLANG_GUEST_CASE vfork_guest_inherits_blocked_mask_and_restores_parent");
    Ok(())
}
