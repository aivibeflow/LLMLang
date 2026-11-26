//! Voluntary entry into tracing by the calling process's parent.
use crate::{abi, decode_zero, SyscallError};

const PTRACE: usize = 101;

/// Request tracing of the calling process by its parent (PTRACE_TRACEME).
pub fn ptrace_trace_me() -> Result<(), SyscallError> {
    decode_zero(unsafe { abi::call(PTRACE, [0; 6]) })
}
