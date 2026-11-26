//! Native zero-argument restart entry.

use crate::{abi, decode_nonnegative, SyscallError};

const RESTART_SYSCALL: usize = 219;

/// Calls the current thread's native restart entry from ordinary user context.
/// Linux returns EINTR when the thread has no restart operation pending.
pub fn restart_syscall() -> Result<usize, SyscallError> {
    decode_nonnegative(unsafe { abi::invoke(RESTART_SYSCALL, [0; 6]) })
}
