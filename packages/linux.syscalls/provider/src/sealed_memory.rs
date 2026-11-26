//! User-mode memory facilities, with no external address parameters.
use std::{fmt, mem::ManuallyDrop};

use crate::{abi, decode_zero, LinuxFd, Mapping, SyscallError, O_CLOEXEC, O_NONBLOCK};

const USERFAULTFD: usize = 323;
const MEMFD_SECRET: usize = 447;
const MSEAL: usize = 462;
const UFFD_USER_MODE_ONLY: usize = 1;

/// Create a close-on-exec nonblocking descriptor for user-mode faults only.
pub fn userfaultfd() -> Result<LinuxFd, SyscallError> {
    LinuxFd::from_result(unsafe {
        abi::invoke(
            USERFAULTFD,
            [
                UFFD_USER_MODE_ONLY | (O_CLOEXEC | O_NONBLOCK) as usize,
                0,
                0,
                0,
                0,
                0,
            ],
        )
    })
}

/// Create a close-on-exec descriptor for a Linux secret-memory file.
pub fn memfd_secret() -> Result<LinuxFd, SyscallError> {
    LinuxFd::from_result(unsafe { abi::invoke(MEMFD_SECRET, [O_CLOEXEC as usize, 0, 0, 0, 0, 0]) })
}

/// A sealed, readable mapping. Linux keeps it mapped until the process exits.
pub struct SealedMapping {
    mapping: ManuallyDrop<Mapping>,
}

impl SealedMapping {
    pub fn as_slice(&self) -> &[u8] {
        self.mapping.as_slice()
    }
}

#[derive(Debug)]
pub struct SealMappingError {
    error: SyscallError,
    mapping: Mapping,
}

impl SealMappingError {
    pub fn into_parts(self) -> (SyscallError, Mapping) {
        (self.error, self.mapping)
    }
}

impl fmt::Display for SealMappingError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        self.error.fmt(formatter)
    }
}

impl std::error::Error for SealMappingError {}

/// Seal all pages of an owned mapping. On failure retain the mapping.
pub fn mseal(mapping: Mapping) -> Result<SealedMapping, SealMappingError> {
    let bytes = mapping.as_slice();
    let raw = unsafe { abi::invoke(MSEAL, [bytes.as_ptr() as usize, bytes.len(), 0, 0, 0, 0]) };
    if let Err(error) = decode_zero(raw) {
        return Err(SealMappingError { error, mapping });
    }
    Ok(SealedMapping {
        mapping: ManuallyDrop::new(mapping),
    })
}
