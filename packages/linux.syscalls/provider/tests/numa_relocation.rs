use linux_syscalls_provider::*;

const EPERM: i32 = 1;
const ENOENT: i32 = 2;
const EOPNOTSUPP: i32 = 95;
const PAGE_SIZE: usize = 4096;

#[test]
fn numa_relocation_checks_owned_page_bounds_and_mask_shape() {
    let mut mapping = mmap(PAGE_SIZE + 1, Protection::ReadWrite).unwrap();
    for offsets in [&[][..], &[1][..], &[PAGE_SIZE * 2][..], &[usize::MAX][..]] {
        assert!(matches!(
            move_pages(&mapping, offsets),
            Err(SyscallError::InvalidInput(_))
        ));
    }
    assert!(matches!(
        move_pages(&mapping, &[0; 1025]),
        Err(SyscallError::InvalidInput(_))
    ));
    assert!(matches!(
        set_mempolicy_home_node(&mut mapping, 1024),
        Err(SyscallError::InvalidInput(_))
    ));
    let empty = NumaNodeMask::from_nodes(&[]).unwrap();
    let node = NumaNodeMask::from_nodes(&[0]).unwrap();
    assert!(matches!(
        migrate_pages(&empty, &node),
        Err(SyscallError::InvalidInput(_))
    ));
    assert!(matches!(
        migrate_pages(&node, &empty),
        Err(SyscallError::InvalidInput(_))
    ));
    munmap(mapping).unwrap();
}

#[test]
fn numa_relocation_native_reports_pages_and_home_policy_or_kernel_errno() {
    let mut mapping = mmap(2 * PAGE_SIZE, Protection::ReadWrite).unwrap();
    mapping.as_mut_slice().unwrap()[0] = 97;
    match move_pages(&mapping, &[PAGE_SIZE, 0, 0]) {
        Ok(status) => {
            assert_eq!(status[0].unwrap_err().code(), ENOENT);
            assert!(status[1].is_ok());
            assert_eq!(status[1], status[2]);
        }
        Err(error) => assert!(
            [EPERM, ENOSYS, EOPNOTSUPP]
                .iter()
                .any(|&code| error.is_errno(code)),
            "{error}"
        ),
    }
    let error = set_mempolicy_home_node(&mut mapping, 0).unwrap_err();
    assert!(
        [ENOENT, EPERM, ENOSYS, EINVAL, EOPNOTSUPP]
            .iter()
            .any(|&code| error.is_errno(code)),
        "{error}"
    );
    assert_eq!(mapping.as_slice()[0], 97);
    munmap(mapping).unwrap();
}
