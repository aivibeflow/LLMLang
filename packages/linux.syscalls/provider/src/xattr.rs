use super::{abi, decode_nonnegative, decode_write, decode_zero, SyscallError};
use std::ffi::CStr;
use std::os::fd::{AsRawFd, BorrowedFd};

const SETXATTR: usize = 188;
const LSETXATTR: usize = 189;
const FSETXATTR: usize = 190;
const GETXATTR: usize = 191;
const LGETXATTR: usize = 192;
const FGETXATTR: usize = 193;
const LISTXATTR: usize = 194;
const LLISTXATTR: usize = 195;
const FLISTXATTR: usize = 196;
const REMOVEXATTR: usize = 197;
const LREMOVEXATTR: usize = 198;
const FREMOVEXATTR: usize = 199;

#[repr(u32)]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum XattrMode {
    Upsert = 0,
    Create = 1,
    Replace = 2,
}

/// Sets an attribute on the file reached by following the path.
pub fn setxattr(
    path: &CStr,
    name: &CStr,
    value: &[u8],
    mode: XattrMode,
) -> Result<(), SyscallError> {
    set(SETXATTR, path.as_ptr() as usize, name, value, mode)
}

/// Sets an attribute without following a final symbolic link.
pub fn lsetxattr(
    path: &CStr,
    name: &CStr,
    value: &[u8],
    mode: XattrMode,
) -> Result<(), SyscallError> {
    set(LSETXATTR, path.as_ptr() as usize, name, value, mode)
}

pub fn fsetxattr(
    fd: BorrowedFd<'_>,
    name: &CStr,
    value: &[u8],
    mode: XattrMode,
) -> Result<(), SyscallError> {
    set(FSETXATTR, fd.as_raw_fd() as usize, name, value, mode)
}

/// Queries the value size with `None` or an empty buffer, otherwise copies the
/// value. A concurrent size change can make a subsequent copy fail with ERANGE.
pub fn getxattr(
    path: &CStr,
    name: &CStr,
    buffer: Option<&mut [u8]>,
) -> Result<usize, SyscallError> {
    get(GETXATTR, path.as_ptr() as usize, name, buffer)
}

/// Queries or copies the value without following a final symbolic link.
pub fn lgetxattr(
    path: &CStr,
    name: &CStr,
    buffer: Option<&mut [u8]>,
) -> Result<usize, SyscallError> {
    get(LGETXATTR, path.as_ptr() as usize, name, buffer)
}

pub fn fgetxattr(
    fd: BorrowedFd<'_>,
    name: &CStr,
    buffer: Option<&mut [u8]>,
) -> Result<usize, SyscallError> {
    get(FGETXATTR, fd.as_raw_fd() as usize, name, buffer)
}

/// Queries the list byte size with `None` or an empty buffer, otherwise copies
/// NUL-terminated names in kernel order. The result includes name terminators.
pub fn listxattr(path: &CStr, buffer: Option<&mut [u8]>) -> Result<usize, SyscallError> {
    list(LISTXATTR, path.as_ptr() as usize, buffer)
}

/// Queries or copies the list without following a final symbolic link.
pub fn llistxattr(path: &CStr, buffer: Option<&mut [u8]>) -> Result<usize, SyscallError> {
    list(LLISTXATTR, path.as_ptr() as usize, buffer)
}

pub fn flistxattr(fd: BorrowedFd<'_>, buffer: Option<&mut [u8]>) -> Result<usize, SyscallError> {
    list(FLISTXATTR, fd.as_raw_fd() as usize, buffer)
}

/// Removes an attribute from the file reached by following the path.
pub fn removexattr(path: &CStr, name: &CStr) -> Result<(), SyscallError> {
    remove(REMOVEXATTR, path.as_ptr() as usize, name)
}

/// Removes an attribute without following a final symbolic link.
pub fn lremovexattr(path: &CStr, name: &CStr) -> Result<(), SyscallError> {
    remove(LREMOVEXATTR, path.as_ptr() as usize, name)
}

pub fn fremovexattr(fd: BorrowedFd<'_>, name: &CStr) -> Result<(), SyscallError> {
    remove(FREMOVEXATTR, fd.as_raw_fd() as usize, name)
}

// The subject word is supplied by one of the typed public wrappers and is
// either its still-live C pathname or the number of its borrowed descriptor.
fn set(
    number: usize,
    subject: usize,
    name: &CStr,
    value: &[u8],
    mode: XattrMode,
) -> Result<(), SyscallError> {
    decode_zero(unsafe {
        abi::invoke(
            number,
            [
                subject,
                name.as_ptr() as usize,
                value.as_ptr() as usize,
                value.len(),
                mode as usize,
                0,
            ],
        )
    })
}

fn get(
    number: usize,
    subject: usize,
    name: &CStr,
    buffer: Option<&mut [u8]>,
) -> Result<usize, SyscallError> {
    with_buffer(buffer, |address, length| unsafe {
        abi::invoke(
            number,
            [subject, name.as_ptr() as usize, address, length, 0, 0],
        )
    })
}

fn list(number: usize, subject: usize, buffer: Option<&mut [u8]>) -> Result<usize, SyscallError> {
    with_buffer(buffer, |address, length| unsafe {
        abi::invoke(number, [subject, address, length, 0, 0, 0])
    })
}

fn remove(number: usize, subject: usize, name: &CStr) -> Result<(), SyscallError> {
    decode_zero(unsafe { abi::invoke(number, [subject, name.as_ptr() as usize, 0, 0, 0, 0]) })
}

fn with_buffer(
    buffer: Option<&mut [u8]>,
    syscall: impl FnOnce(usize, usize) -> isize,
) -> Result<usize, SyscallError> {
    match buffer {
        Some(buffer) if !buffer.is_empty() => {
            let length = buffer.len();
            decode_write(syscall(buffer.as_mut_ptr() as usize, length), length)
        }
        _ => decode_nonnegative(syscall(0, 0)),
    }
}
