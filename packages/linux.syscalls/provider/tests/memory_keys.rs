use linux_syscalls_provider::{mmap, munmap, pkey_alloc, pkey_free, pkey_mprotect, Protection};

#[test]
fn pkey_mprotect_key_zero_preserves_owned_mapping() {
    let mut mapping = mmap(4097, Protection::ReadWrite).unwrap();
    let base = mapping.as_slice().as_ptr();
    mapping.as_mut_slice().unwrap()[4096] = 0xa5;
    let readonly = pkey_mprotect(&mut mapping, Protection::ReadOnly);
    assert_eq!(mapping.as_slice().as_ptr(), base);
    assert_eq!(mapping.as_slice().len(), 4097);
    assert_eq!(mapping.as_slice()[4096], 0xa5);
    assert!(mapping.as_mut_slice().is_none());
    if let Err(error) = readonly {
        assert!(
            [1, 13, 22, 38]
                .into_iter()
                .any(|errno| error.is_errno(errno)),
            "{error:?}"
        );
        munmap(mapping).unwrap();
        return;
    }
    pkey_mprotect(&mut mapping, Protection::ReadWrite).unwrap();
    mapping.as_mut_slice().unwrap()[0] = 0x5a;
    assert_eq!(
        (mapping.as_slice()[0], mapping.as_slice()[4096]),
        (0x5a, 0xa5)
    );
    munmap(mapping).unwrap();
}

#[test]
fn pkey_alloc_reports_host_availability_without_changing_mapping() {
    let mut mapping = mmap(1, Protection::ReadWrite).unwrap();
    mapping.as_mut_slice().unwrap()[0] = 0x5a;
    match pkey_alloc() {
        Ok(key) => pkey_free(key).unwrap(),
        Err(error) => assert!(
            [1, 13, 22, 28, 38]
                .into_iter()
                .any(|errno| error.is_errno(errno)),
            "{error:?}"
        ),
    }
    assert_eq!(mapping.as_slice(), &[0x5a]);
    munmap(mapping).unwrap();
}
