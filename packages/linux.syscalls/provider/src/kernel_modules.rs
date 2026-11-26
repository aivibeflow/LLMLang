use super::{abi, decode_zero, fcntl_getfl, fstat, SyscallError, O_NONBLOCK, O_RDONLY};
use std::ffi::CStr;
use std::os::fd::{AsRawFd, BorrowedFd};

const INIT_MODULE: usize = 175;
const DELETE_MODULE: usize = 176;
const FINIT_MODULE: usize = 313;

const O_ACCMODE: i32 = 0o3;
const O_PATH: i32 = 0o10000000;
const S_IFMT: u32 = 0o170000;
const S_IFREG: u32 = 0o100000;
// Linux v6.12 MODULE_NAME_LEN is 64 - sizeof(unsigned long), including NUL.
const MAX_MODULE_NAME_BYTES: usize = 55;

/// Loads a trusted, uncompressed native module from an immutable byte slice.
/// Linux reads the bytes and checks privileges, format and signature policy.
/// The operation can affect the whole kernel. Module parameters are empty.
pub fn init_module(image: &[u8]) -> Result<(), SyscallError> {
    if image.is_empty() {
        return Err(SyscallError::InvalidInput("empty kernel module image"));
    }
    // Linux copies the supplied byte range and parameter string during entry.
    let raw = unsafe {
        abi::call(
            INIT_MODULE,
            [
                image.as_ptr() as usize,
                image.len(),
                c"".as_ptr() as usize,
                0,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)
}

/// Loads a trusted, uncompressed native module from a read-only regular file.
/// The descriptor remains borrowed. Linux reads from offset zero without
/// changing the file offset. The caller keeps the file content stable during
/// the call. Module parameters and flags are fixed to their empty defaults.
pub fn finit_module(image: BorrowedFd<'_>) -> Result<(), SyscallError> {
    if fcntl_getfl(image)? & (O_ACCMODE | O_PATH) != O_RDONLY
        || fstat(image)?.mode & S_IFMT != S_IFREG
    {
        return Err(SyscallError::InvalidInput(
            "kernel module requires an open read-only regular file",
        ));
    }
    // The borrow keeps the descriptor valid throughout validation and load.
    let raw = unsafe {
        abi::call(
            FINIT_MODULE,
            [
                image.as_raw_fd() as usize,
                c"".as_ptr() as usize,
                0,
                0,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)
}

/// Requests removal by a bare module name with O_NONBLOCK and no force flags.
/// Linux checks privileges and module state before removing it globally.
pub fn delete_module(name: &CStr) -> Result<(), SyscallError> {
    let bytes = name.to_bytes();
    if bytes.is_empty()
        || bytes.len() > MAX_MODULE_NAME_BYTES
        || bytes
            .iter()
            .any(|byte| !(byte.is_ascii_alphanumeric() || [b'_', b'-'].contains(byte)))
    {
        return Err(SyscallError::InvalidInput("invalid kernel module name"));
    }
    // Linux reads only the validated NUL-terminated name during the call.
    let raw = unsafe {
        abi::call(
            DELETE_MODULE,
            [name.as_ptr() as usize, O_NONBLOCK as usize, 0, 0, 0, 0],
        )
    };
    decode_zero(raw)
}
