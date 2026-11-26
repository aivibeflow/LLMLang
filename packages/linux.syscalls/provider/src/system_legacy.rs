//! Narrow Linux observations and whole-address-space memory lock operations.
use crate::{abi, decode_nonnegative, decode_zero, SyscallError};

const SYSLOG: usize = 103;
const SYSFS: usize = 139;
const MLOCKALL: usize = 151;
const MUNLOCKALL: usize = 152;

const SYSLOG_ACTION_SIZE_BUFFER: usize = 10;
const SYSFS_GET_COUNT: usize = 3;
const MCL_CURRENT: usize = 1;
const MCL_ONFAULT: usize = 4;

/// Observe the size of the Linux kernel log buffer in bytes.
pub fn syslog_buffer_size() -> Result<usize, SyscallError> {
    decode_nonnegative(unsafe { abi::call(SYSLOG, [SYSLOG_ACTION_SIZE_BUFFER, 0, 0, 0, 0, 0]) })
}

/// Observe the number of filesystem types through the legacy sysfs ABI.
pub fn sysfs_count() -> Result<usize, SyscallError> {
    decode_nonnegative(unsafe { abi::call(SYSFS, [SYSFS_GET_COUNT, 0, 0, 0, 0, 0]) })
}

/// Request locking on fault for current mappings. The caller coordinates all
/// users of this address space, including other threads.
pub fn mlockall_current_onfault() -> Result<(), SyscallError> {
    decode_zero(unsafe { abi::call(MLOCKALL, [MCL_CURRENT | MCL_ONFAULT, 0, 0, 0, 0, 0]) })
}

/// Clear memory locks and the future-lock policy for the calling address space.
pub fn munlockall() -> Result<(), SyscallError> {
    decode_zero(unsafe { abi::call(MUNLOCKALL, [0; 6]) })
}
