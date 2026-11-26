use super::{abi, close, decode_zero, LinuxFd, SyscallError, O_CLOEXEC};
use std::mem::size_of;
use std::os::fd::{AsRawFd, BorrowedFd};

const SOCKETPAIR: usize = 53;
const SETSOCKOPT: usize = 54;
const GETSOCKOPT: usize = 55;
const AF_UNIX: usize = 1;
const SOCK_STREAM: usize = 1;
const SOL_SOCKET: usize = 1;
const SO_REUSEADDR: usize = 2;
const SO_TYPE: usize = 3;

/// Creates a connected pair of Unix stream sockets with FD_CLOEXEC on both.
pub fn socketpair() -> Result<(LinuxFd, LinuxFd), SyscallError> {
    let mut descriptors = [-1_i32; 2];
    // Linux writes exactly two descriptor numbers into this local array.
    let raw = unsafe {
        abi::call(
            SOCKETPAIR,
            [
                AF_UNIX,
                SOCK_STREAM | O_CLOEXEC as usize,
                0,
                descriptors.as_mut_ptr() as usize,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)?;
    let [left, right] = descriptors;
    if left >= 0 && right >= 0 && left != right {
        return Ok((
            LinuxFd::from_result(left as isize)?,
            LinuxFd::from_result(right as isize)?,
        ));
    }
    // Settle any distinct descriptor from a malformed success response.
    if left >= 0 {
        let _ = close(LinuxFd::from_result(left as isize)?);
    }
    if right >= 0 && left != right {
        let _ = close(LinuxFd::from_result(right as isize)?);
    }
    Err(SyscallError::UnexpectedReturn(raw))
}

fn get_socket_int(fd: BorrowedFd<'_>, option: usize) -> Result<i32, SyscallError> {
    let mut value = 0_i32;
    let mut len = size_of::<i32>() as u32;
    // SO_TYPE and SO_REUSEADDR both write a native int and a socklen_t.
    let raw = unsafe {
        abi::call(
            GETSOCKOPT,
            [
                fd.as_raw_fd() as usize,
                SOL_SOCKET,
                option,
                (&mut value as *mut i32) as usize,
                (&mut len as *mut u32) as usize,
                0,
            ],
        )
    };
    decode_zero(raw)?;
    if len as usize != size_of::<i32>() {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    Ok(value)
}

/// Returns the Linux SO_TYPE socket-kind code, such as 1 for SOCK_STREAM.
pub fn getsockopt_type(fd: BorrowedFd<'_>) -> Result<i32, SyscallError> {
    get_socket_int(fd, SO_TYPE)
}

/// Observes whether SOL_SOCKET/SO_REUSEADDR is enabled.
pub fn getsockopt_reuseaddr(fd: BorrowedFd<'_>) -> Result<bool, SyscallError> {
    Ok(get_socket_int(fd, SO_REUSEADDR)? != 0)
}

/// Updates SOL_SOCKET/SO_REUSEADDR without consuming the socket descriptor.
pub fn setsockopt_reuseaddr(fd: BorrowedFd<'_>, enabled: bool) -> Result<(), SyscallError> {
    let value = i32::from(enabled);
    // Linux reads one native int: 1 enables the option and 0 disables it.
    decode_zero(unsafe {
        abi::call(
            SETSOCKOPT,
            [
                fd.as_raw_fd() as usize,
                SOL_SOCKET,
                SO_REUSEADDR,
                (&value as *const i32) as usize,
                size_of::<i32>(),
                0,
            ],
        )
    })
}
