//! Descriptor replacement and directory-constrained path resolution.
use std::ffi::CStr;
use std::fmt;
use std::os::fd::{AsRawFd, BorrowedFd};

use crate::{abi, decode_nonnegative, LinuxFd, OpenOptions, SyscallError, O_CLOEXEC};

const DUP2: usize = 33;
const DUP3: usize = 292;
const OPENAT2: usize = 437;
pub(super) const RESOLVE_NO_MAGICLINKS: u64 = 0x02;
pub(super) const RESOLVE_BENEATH: u64 = 0x08;

#[derive(Debug)]
pub struct DupReplacementError {
    error: SyscallError,
    target: LinuxFd,
}

impl DupReplacementError {
    pub fn into_parts(self) -> (SyscallError, LinuxFd) {
        (self.error, self.target)
    }
}

impl fmt::Display for DupReplacementError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        self.error.fmt(formatter)
    }
}

impl std::error::Error for DupReplacementError {}

fn replace(
    number: usize,
    source: BorrowedFd<'_>,
    target: LinuxFd,
    flags: i32,
) -> Result<LinuxFd, DupReplacementError> {
    let target_number = target.as_raw_fd() as usize;
    let raw = unsafe {
        abi::call(
            number,
            [
                source.as_raw_fd() as usize,
                target_number,
                flags as usize,
                0,
                0,
                0,
            ],
        )
    };
    match decode_nonnegative(raw) {
        Ok(observed) if observed == target_number => Ok(target),
        Ok(_) => Err(DupReplacementError {
            error: SyscallError::UnexpectedReturn(raw),
            target,
        }),
        Err(error) => Err(DupReplacementError { error, target }),
    }
}

pub fn dup2(source: BorrowedFd<'_>, target: LinuxFd) -> Result<LinuxFd, DupReplacementError> {
    replace(DUP2, source, target, 0)
}

pub fn dup3(
    source: BorrowedFd<'_>,
    target: LinuxFd,
    cloexec: bool,
) -> Result<LinuxFd, DupReplacementError> {
    replace(DUP3, source, target, if cloexec { O_CLOEXEC } else { 0 })
}

#[repr(C)]
struct OpenHow {
    flags: u64,
    mode: u64,
    resolve: u64,
}

const _: () = assert!(std::mem::size_of::<OpenHow>() == 24);

/// Resolve with Linux RESOLVE_BENEATH and RESOLVE_NO_MAGICLINKS semantics.
pub fn openat2_beneath(
    directory: BorrowedFd<'_>,
    path: &CStr,
    options: OpenOptions,
) -> Result<LinuxFd, SyscallError> {
    openat2_resolve(
        directory,
        path,
        options,
        RESOLVE_BENEATH | RESOLVE_NO_MAGICLINKS,
    )
}

pub(super) fn openat2_resolve(
    directory: BorrowedFd<'_>,
    path: &CStr,
    options: OpenOptions,
    resolve: u64,
) -> Result<LinuxFd, SyscallError> {
    let how = OpenHow {
        flags: (options.flags | O_CLOEXEC) as u32 as u64,
        mode: u64::from(options.mode),
        resolve,
    };
    LinuxFd::from_result(unsafe {
        abi::call(
            OPENAT2,
            [
                directory.as_raw_fd() as usize,
                path.as_ptr() as usize,
                std::ptr::from_ref(&how) as usize,
                std::mem::size_of::<OpenHow>(),
                0,
                0,
            ],
        )
    })
}
