use linux_syscalls_provider::{mmap, mprotect, mremap, munmap, Protection, SyscallError};

#[test]
fn remap_preserves_prefix_and_page_rounded_tail() {
    let mut mapping = mmap(8192, Protection::ReadWrite).unwrap();
    {
        let bytes = mapping.as_mut_slice().unwrap();
        bytes[0] = 0x12;
        bytes[4096] = 0x34;
        bytes[5000] = 0x56;
    }

    mremap(&mut mapping, 4097).unwrap();
    assert_eq!(mapping.as_slice().len(), 4097);
    assert_eq!(mapping.as_slice()[4096], 0x34);
    mremap(&mut mapping, 8193).unwrap();
    assert_eq!(mapping.as_slice().len(), 8193);
    assert_eq!(mapping.as_slice()[0], 0x12);
    assert_eq!(mapping.as_slice()[5000], 0x56);
    assert_eq!(mapping.as_slice()[8192], 0);

    mremap(&mut mapping, 1).unwrap();
    mremap(&mut mapping, 8193).unwrap();
    assert_eq!(mapping.as_slice()[0], 0x12);
    assert!(mapping.as_slice()[4096..].iter().all(|byte| *byte == 0));
    munmap(mapping).unwrap();
}

#[test]
fn remap_failure_retains_original_mapping_and_permissions() {
    let mut mapping = mmap(4097, Protection::ReadWrite).unwrap();
    mapping.as_mut_slice().unwrap()[4096] = 0x7b;
    mprotect(&mut mapping, Protection::ReadOnly).unwrap();
    for length in [0, usize::MAX] {
        assert!(matches!(
            mremap(&mut mapping, length),
            Err(SyscallError::InvalidInput(_))
        ));
    }
    // The request is representable as isize, but exceeds even the five-level
    // page-table virtual address space on x86-64.
    let error = mremap(&mut mapping, isize::MAX as usize / 2).unwrap_err();
    // Linux may reject this at a range check (EINVAL) or while finding an
    // available range (ENOMEM), depending on the kernel version.
    assert!(
        error.is_errno(22) || error.is_errno(12),
        "oversized remap returned {error:?}"
    );
    assert_eq!(mapping.as_slice().len(), 4097);
    assert_eq!(mapping.as_slice()[4096], 0x7b);
    assert!(mapping.as_mut_slice().is_none());

    mremap(&mut mapping, 16385).unwrap();
    assert_eq!(mapping.as_slice().len(), 16385);
    assert_eq!(mapping.as_slice()[4096], 0x7b);
    assert!(mapping.as_mut_slice().is_none());
    munmap(mapping).unwrap();
}
