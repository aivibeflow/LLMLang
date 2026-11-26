use linux_syscalls_provider::*;

const E2BIG: i32 = 7;
const EOPNOTSUPP: i32 = 95;
const EPERM: i32 = 1;

fn assert_observed_availability<T: std::fmt::Debug>(
    operation: &str,
    result: Result<LsmQuery<T>, SyscallError>,
) {
    match result {
        Ok(LsmQuery::Complete(value)) => eprintln!("{operation}: zero-capacity result {value:?}"),
        Ok(LsmQuery::BufferTooSmall {
            required_bytes,
            errno,
        }) => {
            assert!(required_bytes > 0);
            assert!(errno.is_errno(E2BIG));
        }
        Err(error) => {
            assert!(
                [EPERM, ENOSYS, EOPNOTSUPP]
                    .iter()
                    .any(|code| error.is_errno(*code)),
                "{operation}: {error}"
            );
            eprintln!("{operation}: host-profile outcome {error}");
        }
    }
}

#[test]
fn lsm_native_queries_preserve_host_availability() {
    assert_observed_availability("lsm_list_modules", lsm_list_modules(0));
    assert_observed_availability("lsm_get_self_attr", lsm_get_self_attr(0));
}

#[test]
fn lsm_queries_reject_excessive_capacity_before_kernel_access() {
    assert!(matches!(
        lsm_list_modules(2049),
        Err(SyscallError::InvalidInput(_))
    ));
    assert!(matches!(
        lsm_get_self_attr(65_537),
        Err(SyscallError::InvalidInput(_))
    ));
}
