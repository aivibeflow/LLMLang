use linux_syscalls_provider::*;

#[test]
fn sysv_shared_memory_tracks_attach_detach_and_remove() {
    let mut segment = shmget(123).unwrap();
    let initial = shmctl_stat(&segment).unwrap();
    assert_eq!(initial.size, 123);
    assert_eq!(initial.permissions, 0o600);
    assert_eq!(initial.creator_pid, getpid().unwrap());
    assert_eq!(initial.attachments, 0);
    assert!(!initial.marked_for_removal);

    let mut first = shmat(&segment).unwrap();
    let mut second = shmat(&segment).unwrap();
    let attached = shmctl_stat(&segment).unwrap();
    assert_eq!(attached.attachments, 2);
    assert_eq!(attached.last_operator_pid, getpid().unwrap());

    shmdt(&mut first).unwrap();
    assert_eq!(shmctl_stat(&segment).unwrap().attachments, 1);
    shmctl_rmid(&mut segment).unwrap();
    shmdt(&mut second).unwrap();
}

#[test]
fn sysv_shared_memory_preserves_kernel_errno_and_rejects_consumed_handles() {
    assert!(shmget(0).unwrap_err().is_errno(EINVAL));
    let mut segment = shmget(1).unwrap();
    let mut attached = shmat(&segment).unwrap();

    shmdt(&mut attached).unwrap();
    assert!(matches!(
        shmdt(&mut attached),
        Err(SyscallError::InvalidInput(_))
    ));

    shmctl_rmid(&mut segment).unwrap();
    assert!(matches!(
        shmctl_stat(&segment),
        Err(SyscallError::InvalidInput(_))
    ));
    assert!(matches!(
        shmat(&segment),
        Err(SyscallError::InvalidInput(_))
    ));
    assert!(matches!(
        shmctl_rmid(&mut segment),
        Err(SyscallError::InvalidInput(_))
    ));
}

#[test]
fn sysv_shared_memory_drop_detaches_and_removes() {
    let segment = shmget(64).unwrap();
    let first = shmat(&segment).unwrap();
    {
        let second = shmat(&segment).unwrap();
        assert_eq!(shmctl_stat(&segment).unwrap().attachments, 2);
        drop(second);
    }
    assert_eq!(shmctl_stat(&segment).unwrap().attachments, 1);

    // Segment removal is deferred until the remaining attachment closes.
    drop(segment);
    let mut first = first;
    shmdt(&mut first).unwrap();
}
