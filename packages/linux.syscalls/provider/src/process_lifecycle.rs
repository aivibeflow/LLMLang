//! Current-process group and exit operations.
use std::convert::Infallible;

use crate::{abi, decode_nonnegative, decode_zero, SyscallError};

const SETPGID: usize = 109;
const GETPGRP: usize = 111;
const SETSID: usize = 112;
const SET_TID_ADDRESS: usize = 218;
const EXIT_GROUP: usize = 231;

pub fn getpgrp() -> Result<i32, SyscallError> {
    let raw = unsafe { abi::call(GETPGRP, [0; 6]) };
    i32::try_from(decode_nonnegative(raw)?).map_err(|_| SyscallError::UnexpectedReturn(raw))
}

/// Establish the caller's own group, with the caller PID as its group ID.
pub fn setpgid_self() -> Result<(), SyscallError> {
    decode_zero(unsafe { abi::call(SETPGID, [0; 6]) })
}

pub fn setsid() -> Result<i32, SyscallError> {
    let raw = unsafe { abi::call(SETSID, [0; 6]) };
    match i32::try_from(decode_nonnegative(raw)?) {
        Ok(id) if id > 0 => Ok(id),
        _ => Err(SyscallError::UnexpectedReturn(raw)),
    }
}

/// On success Linux exits the current thread group without calling Rust
/// destructors. An externally denied call may return an errno.
pub fn exit_group(status: i32) -> Result<Infallible, SyscallError> {
    let raw = unsafe { abi::call(EXIT_GROUP, [status as usize, 0, 0, 0, 0, 0]) };
    decode_nonnegative(raw)?;
    Err(SyscallError::UnexpectedReturn(raw))
}

/// Disable the caller's clear-child-TID action, then terminate its group
/// without running Rust destructors. If Linux refuses the first call, the
/// error is returned before the change. After it succeeds, returning to
/// normal execution would leave the caller's thread lifecycle inconsistent.
pub fn exit_group_without_clear_tid(status: i32) -> Result<Infallible, SyscallError> {
    disable_clear_tid()?;
    let _ = exit_group(status);
    std::process::abort()
}

fn disable_clear_tid() -> Result<(), SyscallError> {
    let raw = unsafe { abi::call(SET_TID_ADDRESS, [0; 6]) };
    decode_nonnegative(raw)?;
    if raw == 0 {
        std::process::abort();
    }
    Ok(())
}
