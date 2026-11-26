//! Native path and filesystem-context operations.
use std::ffi::CStr;
use std::os::fd::{AsRawFd, BorrowedFd};

use crate::{abi, decode_nonnegative, decode_write, decode_zero, SyscallError};

const GETCWD: usize = 79;
const CHDIR: usize = 80;
const UMASK: usize = 95;
const GETGROUPS: usize = 115;

/// Return the NUL-terminated prefix that the kernel writes, borrowing it from
/// the caller's buffer. Linux may prefix a path with "(unreachable)".
pub fn getcwd(buffer: &mut [u8]) -> Result<&CStr, SyscallError> {
    let raw = unsafe {
        abi::invoke(
            GETCWD,
            [buffer.as_mut_ptr() as usize, buffer.len(), 0, 0, 0, 0],
        )
    };
    let written = decode_write(raw, buffer.len())?;
    CStr::from_bytes_with_nul(&buffer[..written]).map_err(|_| SyscallError::UnexpectedReturn(raw))
}

/// Replace the working directory of the calling Linux filesystem context.
/// Other threads sharing that context observe the change.
pub fn chdir(path: &CStr) -> Result<(), SyscallError> {
    decode_zero(unsafe { abi::invoke(CHDIR, [path.as_ptr() as usize, 0, 0, 0, 0, 0]) })
}

pub fn fchdir(directory: BorrowedFd<'_>) -> Result<(), SyscallError> {
    decode_zero(unsafe {
        abi::invoke(
            crate::mounts::FCHDIR,
            [directory.as_raw_fd() as usize, 0, 0, 0, 0, 0],
        )
    })
}

/// Set the protection mask of the calling Linux filesystem context and return
/// the previous mask. Other threads sharing that context observe the change.
pub fn umask(mask: u16) -> Result<u16, SyscallError> {
    if mask > 0o777 {
        return Err(SyscallError::InvalidInput(
            "permission mask must fit nine bits",
        ));
    }
    let raw = unsafe { abi::invoke(UMASK, [mask as usize, 0, 0, 0, 0, 0]) };
    match decode_nonnegative(raw)? {
        previous @ 0..=0o777 => Ok(previous as u16),
        _ => Err(SyscallError::UnexpectedReturn(raw)),
    }
}

/// Observe supplementary group IDs. An empty buffer queries the count.
pub fn getgroups(groups: &mut [u32]) -> Result<usize, SyscallError> {
    if groups.len() > i32::MAX as usize {
        return Err(SyscallError::InvalidInput(
            "group buffer length exceeds Linux int",
        ));
    }
    let raw = unsafe {
        abi::invoke(
            GETGROUPS,
            [groups.len(), groups.as_mut_ptr() as usize, 0, 0, 0, 0],
        )
    };
    if groups.is_empty() {
        return decode_nonnegative(raw);
    }
    decode_write(raw, groups.len())
}
