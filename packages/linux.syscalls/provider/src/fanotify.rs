//! A nonblocking fanotify notification group with one borrowed inode mark.
use std::mem::{align_of, offset_of, size_of};
use std::os::fd::{AsRawFd, BorrowedFd};

use crate::{abi, decode_nonnegative, decode_zero, LinuxFd, SyscallError, O_CLOEXEC, O_RDONLY};

const FANOTIFY_INIT: usize = 300;
const FANOTIFY_MARK: usize = 301;
const FAN_CLOEXEC: usize = 1;
const FAN_NONBLOCK: usize = 2;
const FAN_CLASS_NOTIF: usize = 0;
const FANOTIFY_METADATA_VERSION: u8 = 3;
const FAN_NOFD: i32 = -1;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct FanotifyMask(u64);

impl FanotifyMask {
    pub const ACCESS: Self = Self(0x01);
    pub const MODIFY: Self = Self(0x02);
    pub const CLOSE_WRITE: Self = Self(0x08);
    pub const CLOSE_NOWRITE: Self = Self(0x10);
    pub const OPEN: Self = Self(0x20);

    pub const fn combine(self, other: Self) -> Self {
        Self(self.0 | other.0)
    }

    pub const fn bits(self) -> u64 {
        self.0
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u32)]
pub enum FanotifyMarkAction {
    Add = 1,
    Remove = 2,
}

/// Owns the group and keeps its sole marked object borrowed until removal or
/// group teardown. Closing the group discards its marks and pending events.
#[derive(Debug)]
pub struct Fanotify<'fd> {
    group: LinuxFd,
    mark: Option<(BorrowedFd<'fd>, FanotifyMask)>,
}

/// Open a nonblocking notification group. The group and delivered descriptors
/// are close-on-exec. Delivered descriptors are opened read-only.
pub fn fanotify_init<'fd>() -> Result<Fanotify<'fd>, SyscallError> {
    let group = LinuxFd::from_result(unsafe {
        abi::call(
            FANOTIFY_INIT,
            [
                FAN_CLASS_NOTIF | FAN_CLOEXEC | FAN_NONBLOCK,
                (O_RDONLY | O_CLOEXEC) as usize,
                0,
                0,
                0,
                0,
            ],
        )
    })?;
    Ok(Fanotify { group, mark: None })
}

/// Add one inode mark, or remove the same descriptor and mask. A null pathname
/// tells Linux to select the exact object named by the borrowed descriptor.
pub fn fanotify_mark<'fd>(
    instance: &mut Fanotify<'fd>,
    object: BorrowedFd<'fd>,
    action: FanotifyMarkAction,
    mask: FanotifyMask,
) -> Result<(), SyscallError> {
    let next_mark = match (action, instance.mark) {
        (FanotifyMarkAction::Add, None) => Some((object, mask)),
        (FanotifyMarkAction::Remove, Some((marked, marked_mask)))
            if marked.as_raw_fd() == object.as_raw_fd() && marked_mask == mask =>
        {
            None
        }
        (FanotifyMarkAction::Add, Some(_)) => {
            return Err(SyscallError::InvalidInput(
                "fanotify group already has an inode mark",
            ));
        }
        (FanotifyMarkAction::Remove, _) => {
            return Err(SyscallError::InvalidInput(
                "fanotify removal must match the tracked descriptor and mask",
            ));
        }
    };
    decode_zero(unsafe {
        abi::call(
            FANOTIFY_MARK,
            [
                instance.group.as_raw_fd() as usize,
                action as usize,
                mask.bits() as usize,
                object.as_raw_fd() as usize,
                0,
                0,
            ],
        )
    })?;
    instance.mark = next_mark;
    Ok(())
}

#[repr(C)]
struct Metadata {
    event_len: u32,
    version: u8,
    reserved: u8,
    metadata_len: u16,
    mask: u64,
    fd: i32,
    pid: i32,
}

const _: () = {
    assert!(size_of::<Metadata>() == 24);
    assert!(align_of::<Metadata>() == 8);
    assert!(offset_of!(Metadata, mask) == 8);
    assert!(offset_of!(Metadata, fd) == 16);
    assert!(offset_of!(Metadata, pid) == 20);
};

#[derive(Debug)]
pub struct FanotifyEvent {
    pub mask: u64,
    /// Native process ID. Linux may report zero across PID namespaces.
    pub pid: i32,
    /// Owns the descriptor installed by the kernel, when present.
    pub file: Option<LinuxFd>,
}

/// Read one v3 metadata record and take ownership of any delivered descriptor.
/// Linux reports EAGAIN if the nonblocking queue is empty.
pub fn read_fanotify_event(instance: &Fanotify<'_>) -> Result<FanotifyEvent, SyscallError> {
    let size = size_of::<Metadata>();
    let mut metadata = Metadata {
        event_len: 0,
        version: 0,
        reserved: 0,
        metadata_len: 0,
        mask: 0,
        fd: FAN_NOFD,
        pid: 0,
    };
    let raw = unsafe {
        abi::call(
            abi::READ,
            [
                instance.group.as_raw_fd() as usize,
                std::ptr::from_mut(&mut metadata) as usize,
                size,
                0,
                0,
                0,
            ],
        )
    };
    if decode_nonnegative(raw)? != size || metadata.version != FANOTIFY_METADATA_VERSION {
        return Err(SyscallError::UnexpectedReturn(raw));
    }

    // For the v3 layout, acquire the installed descriptor before validation
    // that can fail. Its destructor closes it on either path.
    let file = match metadata.fd {
        FAN_NOFD => None,
        descriptor if descriptor >= 0 => Some(LinuxFd::from_result(descriptor as isize)?),
        _ => return Err(SyscallError::UnexpectedReturn(raw)),
    };
    if metadata.event_len as usize != size
        || metadata.metadata_len as usize != size
        || metadata.reserved != 0
        || metadata.pid < 0
    {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    Ok(FanotifyEvent {
        mask: metadata.mask,
        pid: metadata.pid,
        file,
    })
}
