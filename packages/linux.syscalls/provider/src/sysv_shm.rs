use super::{abi, decode_nonnegative, decode_zero, SyscallError};
use std::fmt;
use std::marker::PhantomData;
use std::mem::{align_of, offset_of, size_of};
use std::rc::Rc;

const SHMGET: usize = 29;
const SHMAT: usize = 30;
const SHMCTL: usize = 31;
const SHMDT: usize = 67;
const IPC_PRIVATE: usize = 0;
const IPC_RMID: usize = 0;
const IPC_STAT: usize = 2;
const SHM_RDONLY: usize = 0o10000;
const SHM_DEST: u32 = 0o1000;
const PERMISSION_BITS: u32 = 0o777;

#[repr(C)]
#[derive(Default)]
struct NativeIpcPermissions {
    key: i32,
    owner_uid: u32,
    owner_gid: u32,
    creator_uid: u32,
    creator_gid: u32,
    mode: u32,
    sequence: u16,
    padding: [u8; 6],
    reserved: [u64; 2],
}

#[repr(C)]
#[derive(Default)]
struct NativeShmStat {
    permissions: NativeIpcPermissions,
    size: usize,
    last_attach: i64,
    last_detach: i64,
    last_change: i64,
    creator_pid: i32,
    last_operator_pid: i32,
    attachments: usize,
    reserved: [u64; 2],
}

const _: () = {
    assert!(size_of::<NativeIpcPermissions>() == 48);
    assert!(align_of::<NativeIpcPermissions>() == 8);
    assert!(offset_of!(NativeIpcPermissions, mode) == 20);
    assert!(offset_of!(NativeIpcPermissions, reserved) == 32);
    assert!(size_of::<NativeShmStat>() == 112);
    assert!(align_of::<NativeShmStat>() == 8);
    assert!(offset_of!(NativeShmStat, size) == 48);
    assert!(offset_of!(NativeShmStat, creator_pid) == 80);
    assert!(offset_of!(NativeShmStat, attachments) == 88);
};

/// Ownership of a private SysV shared memory segment in the caller's IPC
/// namespace. Keep the thread in that namespace and coordinate ownership
/// with external APIs. Dropping attempts IPC_RMID if ownership is still live.
pub struct ShmSegment {
    identifier: Option<i32>,
    thread_affine: PhantomData<Rc<()>>,
}

impl fmt::Debug for ShmSegment {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("ShmSegment")
            .field("active", &self.identifier.is_some())
            .finish()
    }
}

impl Drop for ShmSegment {
    fn drop(&mut self) {
        if let Some(identifier) = self.identifier {
            let _ = remove(identifier);
        }
    }
}

/// Owns one read-only, kernel-placed attachment. It does not expose a
/// pointer or byte slice because other allowed processes may attach the
/// same segment. Its lifetime is independent of the segment owner's.
pub struct ShmAttachment {
    address: Option<usize>,
    thread_affine: PhantomData<Rc<()>>,
}

impl fmt::Debug for ShmAttachment {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("ShmAttachment")
            .field("attached", &self.address.is_some())
            .finish()
    }
}

impl Drop for ShmAttachment {
    fn drop(&mut self) {
        if let Some(address) = self.address {
            let _ = detach(address);
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ShmStat {
    pub size: usize,
    pub attachments: usize,
    pub permissions: u32,
    pub marked_for_removal: bool,
    pub creator_pid: i32,
    pub last_operator_pid: i32,
}

/// Allocates a newly created IPC_PRIVATE segment with mode 0600. Linux
/// checks size and namespace quotas, including invalid zero size.
pub fn shmget(size: usize) -> Result<ShmSegment, SyscallError> {
    let raw = unsafe { abi::call(SHMGET, [IPC_PRIVATE, size, 0o600, 0, 0, 0]) };
    let identifier =
        i32::try_from(decode_nonnegative(raw)?).map_err(|_| SyscallError::UnexpectedReturn(raw))?;
    Ok(ShmSegment {
        identifier: Some(identifier),
        thread_affine: PhantomData,
    })
}

/// Attaches the segment read-only at an address selected by Linux.
pub fn shmat(segment: &ShmSegment) -> Result<ShmAttachment, SyscallError> {
    let identifier = active_identifier(segment)?;
    let raw = unsafe { abi::call(SHMAT, [identifier as usize, 0, SHM_RDONLY, 0, 0, 0]) };
    Ok(ShmAttachment {
        address: Some(decode_nonnegative(raw)?),
        thread_affine: PhantomData,
    })
}

/// Detaches the exact mapping owned by this attachment. Success consumes
/// the attachment, while an error retains the address for later cleanup.
pub fn shmdt(attachment: &mut ShmAttachment) -> Result<(), SyscallError> {
    let address = attachment.address.ok_or(SyscallError::InvalidInput(
        "shared memory attachment already detached",
    ))?;
    detach(address)?;
    attachment.address = None;
    Ok(())
}

/// Queries the selected properties of the owned segment using IPC_STAT.
pub fn shmctl_stat(segment: &ShmSegment) -> Result<ShmStat, SyscallError> {
    stat(active_identifier(segment)?)
}

/// Requests removal with IPC_RMID. Existing attachments remain valid and
/// Linux destroys the segment after its last detach. On success this handle
/// no longer owns the segment. Any returned error leaves it available.
pub fn shmctl_rmid(segment: &mut ShmSegment) -> Result<(), SyscallError> {
    remove(active_identifier(segment)?)?;
    segment.identifier = None;
    Ok(())
}

fn active_identifier(segment: &ShmSegment) -> Result<i32, SyscallError> {
    segment.identifier.ok_or(SyscallError::InvalidInput(
        "shared memory segment already removed",
    ))
}

fn remove(identifier: i32) -> Result<(), SyscallError> {
    decode_zero(unsafe { abi::call(SHMCTL, [identifier as usize, IPC_RMID, 0, 0, 0, 0]) })
}

fn detach(address: usize) -> Result<(), SyscallError> {
    decode_zero(unsafe { abi::call(SHMDT, [address, 0, 0, 0, 0, 0]) })
}

fn stat(identifier: i32) -> Result<ShmStat, SyscallError> {
    let mut native = NativeShmStat::default();
    // The native x86-64 syscall writes the 112-byte shmid64_ds for IPC_STAT.
    let raw = unsafe {
        abi::call(
            SHMCTL,
            [
                identifier as usize,
                IPC_STAT,
                (&mut native as *mut NativeShmStat) as usize,
                0,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)?;
    Ok(ShmStat {
        size: native.size,
        attachments: native.attachments,
        permissions: native.permissions.mode & PERMISSION_BITS,
        marked_for_removal: native.permissions.mode & SHM_DEST != 0,
        creator_pid: native.creator_pid,
        last_operator_pid: native.last_operator_pid,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sysv_shared_memory_kernel_finalizes_marked_segment_after_final_detach() {
        let segment = shmget(4096).unwrap();
        let identifier = active_identifier(&segment).unwrap();
        let mut attached = shmat(&segment).unwrap();
        // The owner's drop calls IPC_RMID. A second handle exists only for
        // the test's native state observation.
        drop(segment);
        let marked = stat(identifier).unwrap();
        assert!(marked.marked_for_removal);
        assert_eq!(marked.attachments, 1);
        shmdt(&mut attached).unwrap();
        let failure = stat(identifier).unwrap_err();
        assert!(failure.is_errno(22) || failure.is_errno(43));
    }
}
