use linux_syscalls_provider::{
    fork_execve, pidfd_open, pidfd_send_signal, wait4, ChildSignal, ExecImage, SyscallError, EINTR,
};

#[test]
fn pidfd_targets_the_owned_child_and_never_retargets_after_reaping() {
    let image = ExecImage::new(c"/bin/sleep", &[c"sleep", c"5"], &[]).unwrap();
    let mut child = fork_execve(&image).unwrap();
    let target = pidfd_open(&child);
    let signals = target.as_ref().map(|target| {
        (
            pidfd_send_signal(target, ChildSignal::Check),
            pidfd_send_signal(target, ChildSignal::Terminate),
        )
    });

    // Reap the bounded-duration fixture even if opening or signaling it failed.
    let status = loop {
        match wait4(&mut child, 0) {
            Err(error) if error.is_errno(EINTR) => continue,
            result => break result.unwrap().unwrap(),
        }
    };

    assert_eq!(signals.unwrap(), (Ok(()), Ok(())));
    assert_eq!(status.signal(), Some(15));
    let target = target.unwrap();
    assert!(pidfd_send_signal(&target, ChildSignal::Check)
        .unwrap_err()
        .is_errno(3)); // ESRCH
    assert!(matches!(
        pidfd_open(&child),
        Err(SyscallError::InvalidInput(_))
    ));
}
