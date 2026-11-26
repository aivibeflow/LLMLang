use linux_syscalls_provider::{madvise, mmap, mprotect, munmap, Advice, Protection, SyscallError};

#[test]
fn anonymous_region_changes_permissions_without_losing_contents() {
    let mut mapping = mmap(4097, Protection::ReadOnly).unwrap();
    assert_eq!(mapping.as_slice().len(), 4097);
    assert!(mapping.as_slice().iter().all(|byte| *byte == 0));
    assert!(mapping.as_mut_slice().is_none());

    mprotect(&mut mapping, Protection::ReadWrite).unwrap();
    let bytes = mapping.as_mut_slice().unwrap();
    bytes[0] = 0xa5;
    bytes[4096] = 0x5a;

    mprotect(&mut mapping, Protection::ReadOnly).unwrap();
    assert!(mapping.as_mut_slice().is_none());
    assert_eq!(mapping.as_slice()[0], 0xa5);
    assert_eq!(mapping.as_slice()[4096], 0x5a);
    munmap(mapping).unwrap();
}

#[test]
fn memory_advice_discards_only_the_owned_region_on_dont_need() {
    let mut advised = mmap(4097, Protection::ReadWrite).unwrap();
    let mut other = mmap(4097, Protection::ReadWrite).unwrap();
    advised.as_mut_slice().unwrap().fill(0x5a);
    other.as_mut_slice().unwrap().fill(0xa5);

    for advice in [
        Advice::Normal,
        Advice::Random,
        Advice::Sequential,
        Advice::WillNeed,
    ] {
        madvise(&mut advised, advice).unwrap();
        assert!(advised.as_slice().iter().all(|byte| *byte == 0x5a));
    }
    madvise(&mut advised, Advice::DontNeed).unwrap();
    assert!(advised.as_slice().iter().all(|byte| *byte == 0));
    assert!(other.as_slice().iter().all(|byte| *byte == 0xa5));
    munmap(advised).unwrap();
    munmap(other).unwrap();
}

#[test]
fn invalid_lengths_are_rejected_before_the_kernel_call() {
    for length in [0, usize::MAX] {
        assert!(matches!(
            mmap(length, Protection::ReadWrite),
            Err(SyscallError::InvalidInput(_))
        ));
    }
}

#[test]
fn mapping_larger_than_native_virtual_address_space_reports_enomem() {
    // Even x86-64 with five-level page tables cannot address this range.
    let error = mmap(isize::MAX as usize / 2, Protection::ReadOnly).unwrap_err();
    assert!(error.is_errno(12));
}
