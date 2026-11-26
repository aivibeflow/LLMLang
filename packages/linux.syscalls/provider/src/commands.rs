//! Selected typed commands from the Linux v6.12 x86-64 UAPI.

use super::{abi, decode_nonnegative, decode_zero, SyscallError};
use std::os::fd::{AsRawFd, BorrowedFd};

const F_GETFD: usize = 1;
const F_GETFL: usize = 3;
const FIONREAD: usize = 0x541b;
const PR_GET_NO_NEW_PRIVS: usize = 39;

fn fcntl_flags(fd: BorrowedFd<'_>, command: usize) -> Result<i32, SyscallError> {
    // Both supported commands are getters with no third argument.
    let raw = unsafe { abi::call(abi::FCNTL, [fd.as_raw_fd() as usize, command, 0, 0, 0, 0]) };
    i32::try_from(decode_nonnegative(raw)?).map_err(|_| SyscallError::UnexpectedReturn(raw))
}

/// Reads the descriptor flags, including FD_CLOEXEC.
pub fn fcntl_getfd(fd: BorrowedFd<'_>) -> Result<i32, SyscallError> {
    fcntl_flags(fd, F_GETFD)
}

/// Reads the file access mode and file status flags.
pub fn fcntl_getfl(fd: BorrowedFd<'_>) -> Result<i32, SyscallError> {
    fcntl_flags(fd, F_GETFL)
}

/// Queries unread bytes where the descriptor implements the FIONREAD UAPI.
pub fn ioctl_fionread(fd: BorrowedFd<'_>) -> Result<i32, SyscallError> {
    let mut available = 0_i32;
    // FIONREAD's supported ioctl implementations write one native C int.
    let raw = unsafe {
        abi::call(
            abi::IOCTL,
            [
                fd.as_raw_fd() as usize,
                FIONREAD,
                (&mut available as *mut i32) as usize,
                0,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)?;
    Ok(available)
}

/// Reads the current thread's no_new_privs flag.
pub fn prctl_get_no_new_privs() -> Result<bool, SyscallError> {
    let raw = unsafe { abi::call(abi::PRCTL, [PR_GET_NO_NEW_PRIVS, 0, 0, 0, 0, 0]) };
    match decode_nonnegative(raw)? {
        0 => Ok(false),
        1 => Ok(true),
        _ => Err(SyscallError::UnexpectedReturn(raw)),
    }
}

const PR_SET_NAME: usize = 15;
const PR_GET_NAME: usize = 16;
const TASK_COMM_LEN: usize = 16;

#[derive(Debug, Eq, PartialEq)]
pub struct ThreadName([u8; TASK_COMM_LEN]);

impl ThreadName {
    pub fn as_c_str(&self) -> &std::ffi::CStr {
        std::ffi::CStr::from_bytes_until_nul(&self.0).expect("validated Linux thread name")
    }
}

pub fn prctl_get_name() -> Result<ThreadName, SyscallError> {
    let mut bytes = [0; TASK_COMM_LEN];
    let raw = unsafe {
        abi::call(
            abi::PRCTL,
            [PR_GET_NAME, bytes.as_mut_ptr() as usize, 0, 0, 0, 0],
        )
    };
    decode_zero(raw)?;
    if !bytes.contains(&0) {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    Ok(ThreadName(bytes))
}

pub fn prctl_set_name(name: &std::ffi::CStr) -> Result<(), SyscallError> {
    let name = name.to_bytes_with_nul();
    if name.len() > TASK_COMM_LEN {
        return Err(SyscallError::InvalidInput(
            "Linux thread name exceeds 15 bytes",
        ));
    }
    let mut bytes = [0; TASK_COMM_LEN];
    bytes[..name.len()].copy_from_slice(name);
    decode_zero(unsafe {
        abi::call(
            abi::PRCTL,
            [PR_SET_NAME, bytes.as_ptr() as usize, 0, 0, 0, 0],
        )
    })
}

const PR_SET_NO_NEW_PRIVS: usize = 38;

/// Set no_new_privs on the calling thread. Linux does not permit clearing it.
pub fn prctl_set_no_new_privs() -> Result<(), SyscallError> {
    decode_zero(unsafe { abi::call(abi::PRCTL, [PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0, 0]) })
}
