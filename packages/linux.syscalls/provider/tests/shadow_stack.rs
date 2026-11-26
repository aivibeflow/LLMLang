use linux_syscalls_provider::*;

const EPERM: i32 = 1;
const EOPNOTSUPP: i32 = 95;

#[test]
fn shadow_stack_rejects_invalid_mapping_sizes() {
    for length in [0, isize::MAX as usize + 1, usize::MAX] {
        assert!(matches!(
            map_shadow_stack(length),
            Err(SyscallError::InvalidInput(_))
        ));
    }
}

#[test]
fn shadow_stack_native_observes_owned_mapping_or_kernel_unavailability() {
    match map_shadow_stack(4097) {
        Ok(stack) => {
            assert_eq!(stack.as_slice().len(), 4097);
            assert!(stack.as_slice().iter().all(|&byte| byte == 0));
        }
        Err(error) => assert!(
            [EPERM, ENOSYS, EOPNOTSUPP]
                .iter()
                .any(|&code| error.is_errno(code)),
            "{error}"
        ),
    }
}
