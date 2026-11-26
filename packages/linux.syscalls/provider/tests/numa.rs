use linux_syscalls_provider::*;

const EPERM: i32 = 1;
const EOPNOTSUPP: i32 = 95;

#[test]
fn numa_mask_validates_boundaries_without_syscall() {
    let nodes = NumaNodeMask::from_nodes(&[0, 63, 64, 1023, 64]).unwrap();
    for node in [0, 63, 64, 1023] {
        assert!(nodes.contains(node));
    }
    for node in [1, 62, 65, 1024, u16::MAX] {
        assert!(!nodes.contains(node));
    }
    assert!(!nodes.is_empty());
    assert!(NumaNodeMask::from_nodes(&[]).unwrap().is_empty());
    assert!(matches!(
        NumaNodeMask::from_nodes(&[1024]),
        Err(SyscallError::InvalidInput(_))
    ));
}

#[test]
fn numa_native_reports_policy_or_explicit_unavailability() {
    match get_mempolicy() {
        Ok(policy) => {
            assert!(policy.mode >= 0);
            assert!(!get_mempolicy_allowed().unwrap().is_empty());
            let mapping = mmap(16, Protection::ReadWrite).unwrap();
            assert_eq!(get_mempolicy_mapping(&mapping).unwrap().mode, 0);
            munmap(mapping).unwrap();
        }
        Err(error) => {
            assert!(
                [EPERM, ENOSYS, EOPNOTSUPP, EINVAL]
                    .iter()
                    .any(|code| error.is_errno(*code)),
                "{error}"
            );
            eprintln!("NUMA unavailable in this native profile: {error}");
        }
    }
}
