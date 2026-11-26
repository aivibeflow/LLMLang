//! Read-only file handles derived within an owned temporary mount.
use std::ffi::CStr;
use std::fmt;
use std::marker::PhantomData;
use std::mem::{align_of, offset_of, size_of};
use std::os::fd::AsRawFd;
use std::rc::Rc;

use crate::descriptor_slots::{openat2_resolve, RESOLVE_BENEATH, RESOLVE_NO_MAGICLINKS};
use crate::mounts::{owned_mount_root, O_PATH};
use crate::{
    abi, decode_zero, fstat, LinuxFd, MountedTmpfs, OpenOptions, SyscallError, AT_EMPTY_PATH,
    O_CLOEXEC, O_DIRECTORY, O_RDONLY,
};

const SYNC: usize = 162;
const NAME_TO_HANDLE_AT: usize = 303;
const OPEN_BY_HANDLE_AT: usize = 304;
const HANDLE_CAPACITY: usize = 128;
const AT_HANDLE_MNT_ID_UNIQUE: usize = 0x001;
const RESOLVE_NO_XDEV: u64 = 0x01;
const S_IFMT: u32 = 0o170000;
const S_IFREG: u32 = 0o100000;

/// Wait for Linux to run global writeback on mounted filesystems. The
/// kernel's zero return does not report per-filesystem or writeback errors.
pub fn sync() -> Result<(), SyscallError> {
    decode_zero(unsafe { abi::invoke(SYNC, [0; 6]) })
}

#[repr(C)]
struct NativeFileHandle {
    byte_count: u32,
    handle_type: i32,
    bytes: [u8; HANDLE_CAPACITY],
}

const _: () = {
    assert!(size_of::<NativeFileHandle>() == 136);
    assert!(align_of::<NativeFileHandle>() == 4);
    assert!(offset_of!(NativeFileHandle, bytes) == 8);
};

/// An opaque filesystem handle bound to one live temporary mount and its
/// exact source descriptor. Its native handle bytes cannot be supplied or
/// amended by the caller.
pub struct ScopedFileHandle<'mount> {
    _source: LinuxFd,
    mount_context: LinuxFd,
    native: NativeFileHandle,
    mount_id: u64,
    mount: PhantomData<&'mount Rc<()>>,
}

impl ScopedFileHandle<'_> {
    pub fn mount_id(&self) -> u64 {
        self.mount_id
    }
}

impl fmt::Debug for ScopedFileHandle<'_> {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("ScopedFileHandle")
            .field("mount_id", &self.mount_id)
            .finish_non_exhaustive()
    }
}

/// Encode a regular file inside the borrowed mount. Resolution refuses
/// mount crossings, magic links and escape from the supplied directory.
pub fn name_to_handle_at<'mount>(
    mount: &'mount MountedTmpfs<'_>,
    relative_path: &CStr,
) -> Result<ScopedFileHandle<'mount>, SyscallError> {
    let root = owned_mount_root(mount)?;
    let resolve = RESOLVE_BENEATH | RESOLVE_NO_MAGICLINKS | RESOLVE_NO_XDEV;
    let source = openat2_resolve(
        root.borrow(),
        relative_path,
        OpenOptions {
            flags: O_PATH,
            mode: 0,
        },
        resolve,
    )?;
    if fstat(source.borrow())?.mode & S_IFMT != S_IFREG {
        return Err(SyscallError::InvalidInput(
            "file handle requires a regular file in the temporary mount",
        ));
    }

    let mut native = NativeFileHandle {
        byte_count: HANDLE_CAPACITY as u32,
        handle_type: 0,
        bytes: [0; HANDLE_CAPACITY],
    };
    let mut mount_id = 0u64;
    let raw = unsafe {
        abi::invoke(
            NAME_TO_HANDLE_AT,
            [
                source.as_raw_fd() as usize,
                c"".as_ptr() as usize,
                std::ptr::from_mut(&mut native) as usize,
                std::ptr::from_mut(&mut mount_id) as usize,
                AT_EMPTY_PATH as usize | AT_HANDLE_MNT_ID_UNIQUE,
                0,
            ],
        )
    };
    decode_zero(raw)?;
    let count = native.byte_count as usize;
    if count == 0 || count > HANDLE_CAPACITY || count % size_of::<u32>() != 0 || mount_id == 0 {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    // open_by_handle_at obtains its mount with fdget, which excludes O_PATH.
    // Open an ordinary directory descriptor for the same owned mount.
    let mount_context = openat2_resolve(
        root.borrow(),
        c".",
        OpenOptions {
            flags: O_RDONLY | O_DIRECTORY,
            mode: 0,
        },
        resolve,
    )?;
    Ok(ScopedFileHandle {
        _source: source,
        mount_context,
        native,
        mount_id,
        mount: PhantomData,
    })
}

/// Reopen the encoded object read-only, using the owned ordinary directory
/// descriptor from the original temporary mount for mount selection. Linux can reject unsupported or stale handles.
pub fn open_by_handle_at(handle: &ScopedFileHandle<'_>) -> Result<LinuxFd, SyscallError> {
    LinuxFd::from_result(unsafe {
        abi::invoke(
            OPEN_BY_HANDLE_AT,
            [
                handle.mount_context.as_raw_fd() as usize,
                std::ptr::from_ref(&handle.native) as usize,
                (O_RDONLY | O_CLOEXEC) as usize,
                0,
                0,
                0,
            ],
        )
    })
}
