//! Native swap area activation and deactivation with the default policy.
use std::ffi::CStr;

use crate::{abi, decode_zero, SyscallError};

const SWAPON: usize = 167;
const SWAPOFF: usize = 168;

/// Activate the prepared swap area at a stable path using Linux's default
/// priority and discard policy. The caller coordinates global swap state and
/// keeps the path bound to the same object until deactivation.
pub fn swapon(path: &CStr) -> Result<(), SyscallError> {
    decode_zero(unsafe { abi::call(SWAPON, [path.as_ptr() as usize, 0, 0, 0, 0, 0]) })
}

/// Deactivate the swap area identified by the path. On success Linux has
/// migrated its live pages and released its reference to the backing object.
pub fn swapoff(path: &CStr) -> Result<(), SyscallError> {
    decode_zero(unsafe { abi::call(SWAPOFF, [path.as_ptr() as usize, 0, 0, 0, 0, 0]) })
}
