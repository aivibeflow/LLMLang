//! Fixed read-only native quota-format observations.
use std::ffi::CStr;
use std::os::fd::{AsRawFd, BorrowedFd};

use crate::{abi, decode_zero, SyscallError};

const QUOTACTL: usize = 179;
const QUOTACTL_FD: usize = 443;
const Q_GETFMT: usize = 0x800004 << 8;

/// Quota namespace used to select a format on the target filesystem.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum QuotaKind {
    User = 0,
    Group = 1,
    Project = 2,
}

/// The native format ID returned for active quotas.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum QuotaFormat {
    VfsOld,
    VfsV0,
    Ocfs2,
    VfsV1,
    Shmem,
    Unknown(u32),
}

impl From<u32> for QuotaFormat {
    fn from(id: u32) -> Self {
        match id {
            1 => Self::VfsOld,
            2 => Self::VfsV0,
            3 => Self::Ocfs2,
            4 => Self::VfsV1,
            5 => Self::Shmem,
            id => Self::Unknown(id),
        }
    }
}

/// Read the active quota format of the mounted block device selected by a
/// caller-supplied path. The kernel resolves the path and enforces access.
pub fn quotactl_get_format(device: &CStr, kind: QuotaKind) -> Result<QuotaFormat, SyscallError> {
    let mut format = 0_u32;
    decode_zero(unsafe {
        abi::invoke(
            QUOTACTL,
            [
                Q_GETFMT | kind as usize,
                device.as_ptr() as usize,
                0,
                std::ptr::from_mut(&mut format) as usize,
                0,
                0,
            ],
        )
    })?;
    Ok(format.into())
}

/// Read the active quota format of the filesystem containing the borrowed
/// descriptor. Linux also accepts descriptors opened with `O_PATH`.
pub fn quotactl_fd_get_format(
    file: BorrowedFd<'_>,
    kind: QuotaKind,
) -> Result<QuotaFormat, SyscallError> {
    let mut format = 0_u32;
    decode_zero(unsafe {
        abi::invoke(
            QUOTACTL_FD,
            [
                file.as_raw_fd() as usize,
                Q_GETFMT | kind as usize,
                0,
                std::ptr::from_mut(&mut format) as usize,
                0,
                0,
            ],
        )
    })?;
    Ok(format.into())
}
