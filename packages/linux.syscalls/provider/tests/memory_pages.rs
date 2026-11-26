use linux_syscalls_provider::{
    mincore, mlock, mlock2, mmap, msync, munlock, munmap, MemoryLockMode, MemorySyncMode,
    Protection, SyscallError,
};

#[test]
fn residency_uses_complete_pages_and_preserves_the_destination_suffix() {
    let mut mapping = mmap(4097, Protection::ReadWrite).unwrap();
    let mut short = [0xff; 1];
    assert!(matches!(
        mincore(&mapping, &mut short),
        Err(SyscallError::InvalidInput(_))
    ));
    assert_eq!(short, [0xff]);

    let mut status = [0xff; 3];
    assert_eq!(mincore(&mapping, &mut status).unwrap(), 2);
    assert!(status[..2].iter().all(|byte| *byte <= 1));
    assert_eq!(status[2], 0xff);

    mlock(&mut mapping).unwrap();
    assert_eq!(mincore(&mapping, &mut status).unwrap(), 2);
    assert_eq!(status, [1, 1, 0xff]);
    munlock(&mut mapping).unwrap();
    munmap(mapping).unwrap();
}

#[test]
fn locking_is_not_reference_counted_and_controls_invalidation() {
    let mut mapping = mmap(8192, Protection::ReadWrite).unwrap();
    mlock(&mut mapping).unwrap();
    mlock2(&mut mapping, MemoryLockMode::Immediate).unwrap();
    let busy = msync(&mut mapping, MemorySyncMode::SynchronousInvalidate).unwrap_err();
    assert!(busy.is_errno(16)); // EBUSY

    munlock(&mut mapping).unwrap();
    msync(&mut mapping, MemorySyncMode::SynchronousInvalidate).unwrap();
    munlock(&mut mapping).unwrap();
    munmap(mapping).unwrap();
}

#[test]
fn onfault_lock_and_sync_preserve_anonymous_bytes() {
    let mut mapping = mmap(4097, Protection::ReadWrite).unwrap();
    mlock2(&mut mapping, MemoryLockMode::OnFault).unwrap();
    let bytes = mapping.as_mut_slice().unwrap();
    bytes[0] = 0x69;
    bytes[4096] = 0x96;
    let mut resident = [0; 2];
    assert_eq!(mincore(&mapping, &mut resident).unwrap(), 2);
    assert_eq!(resident, [1, 1]);
    munlock(&mut mapping).unwrap();

    for mode in [
        MemorySyncMode::Asynchronous,
        MemorySyncMode::Synchronous,
        MemorySyncMode::AsynchronousInvalidate,
        MemorySyncMode::SynchronousInvalidate,
    ] {
        msync(&mut mapping, mode).unwrap();
        assert_eq!(mapping.as_slice()[0], 0x69);
        assert_eq!(mapping.as_slice()[4096], 0x96);
    }
    munmap(mapping).unwrap();
}
