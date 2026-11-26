//! Private mount-namespace and fixed tmpfs lifecycle.

use super::uts::UNSHARE;
use super::{
    abi, decode_zero, openat, Directory, LinuxFd, OpenOptions, SyscallError, AT_EMPTY_PATH,
    O_CLOEXEC, O_DIRECTORY, O_NOFOLLOW,
};
use std::cell::Cell;
use std::ffi::CStr;
use std::fmt;
use std::marker::PhantomData;
use std::os::fd::{AsFd, AsRawFd, BorrowedFd};
use std::rc::Rc;

pub(super) const FCHDIR: usize = 81;
const PIVOT_ROOT: usize = 155;
const CHROOT: usize = 161;
const MOUNT: usize = 165;
const UMOUNT2: usize = 166;
const OPEN_TREE: usize = 428;
const MOVE_MOUNT: usize = 429;
const FSOPEN: usize = 430;
const FSCONFIG: usize = 431;
const FSMOUNT: usize = 432;
const FSPICK: usize = 433;
const MOUNT_SETATTR: usize = 442;

const CLONE_NEWNS: usize = 0x0002_0000;
const MS_REC: usize = 16_384;
const MS_PRIVATE: usize = 1 << 18;
const NOSUID_NODEV_NOEXEC: usize = 2 | 4 | 8;
const FSOPEN_CLOEXEC: usize = 1;
const FSMOUNT_CLOEXEC: usize = 1;
const FSCONFIG_SET_STRING: usize = 1;
const FSCONFIG_CMD_CREATE: usize = 6;
const MOVE_MOUNT_EMPTY_PATHS: usize = 0x04 | 0x40;
const MNT_DETACH: usize = 2;
const OPEN_TREE_CLONE: usize = 1;
const FSPICK_CLOEXEC: usize = 1;
const FSPICK_EMPTY_PATH: usize = 8;
const MOUNT_ATTR_RDONLY: u64 = 1;
const MOUNT_ATTR_NOSYMFOLLOW: u64 = 0x0020_0000;
pub(super) const O_PATH: i32 = 0o10000000;

thread_local! {
    static ENTERED: Cell<bool> = const { Cell::new(false) };
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum MountNamespaceError {
    AlreadyEntered,
    Unshare(SyscallError),
    Propagation(SyscallError),
}

impl fmt::Display for MountNamespaceError {
    fn fmt(&self, output: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::AlreadyEntered => {
                output.write_str("mount namespace entry already attempted after a switch")
            }
            Self::Unshare(error) => write!(output, "mount namespace switch failed: {error}"),
            Self::Propagation(error) => write!(
                output,
                "namespace switched but private propagation failed: {error}"
            ),
        }
    }
}

impl std::error::Error for MountNamespaceError {}

/// Exclusive, thread-affine authority for one package-managed attachment.
/// Dropping the token leaves this thread in the private namespace.
#[derive(Debug)]
pub struct PrivateMountNamespace {
    usable: bool,
    thread_affine: PhantomData<Rc<()>>,
}

/// Enters a new mount namespace and makes its mount tree recursively private.
/// If the namespace was entered but propagation fails, no token is issued.
pub fn unshare_mount_private() -> Result<PrivateMountNamespace, MountNamespaceError> {
    if ENTERED.get() {
        return Err(MountNamespaceError::AlreadyEntered);
    }
    decode_zero(unsafe { abi::invoke(UNSHARE, [CLONE_NEWNS, 0, 0, 0, 0, 0]) })
        .map_err(MountNamespaceError::Unshare)?;
    ENTERED.set(true);
    decode_zero(unsafe {
        abi::invoke(
            MOUNT,
            [0, c"/".as_ptr() as usize, 0, MS_REC | MS_PRIVATE, 0, 0],
        )
    })
    .map_err(MountNamespaceError::Propagation)?;
    Ok(PrivateMountNamespace {
        usable: true,
        thread_affine: PhantomData,
    })
}

/// Holds the exact mount root and exclusive authority until detachment.
#[derive(Debug)]
pub struct MountedTmpfs<'ns> {
    namespace: &'ns mut PrivateMountNamespace,
    root: Option<LinuxFd>,
}

/// Attaches a new 1 MiB tmpfs with mode 0700 and nosuid, nodev and noexec.
/// The kernel checks that the destination FD belongs to this namespace.
/// Callers must retain the namespace's private propagation and refrain from
/// externally moving or overmounting the attachment while the handle is live.
pub fn mount_tmpfs<'ns>(
    namespace: &'ns mut PrivateMountNamespace,
    target: BorrowedFd<'_>,
) -> Result<MountedTmpfs<'ns>, SyscallError> {
    if !namespace.usable {
        return Err(SyscallError::InvalidInput(
            "mount namespace requires external recovery",
        ));
    }
    let context = filesystem_context(c"tmpfs")?;
    for (name, value) in [(c"size", c"1048576"), (c"mode", c"0700")] {
        filesystem_option(&context, name, value)?;
    }
    let root = create_detached_filesystem(&context, NOSUID_NODEV_NOEXEC)?;
    let empty = c"".as_ptr() as usize;
    decode_zero(unsafe {
        abi::invoke(
            MOVE_MOUNT,
            [
                root.as_raw_fd() as usize,
                empty,
                target.as_raw_fd() as usize,
                empty,
                MOVE_MOUNT_EMPTY_PATHS,
                0,
            ],
        )
    })?;
    Ok(MountedTmpfs {
        namespace,
        root: Some(root),
    })
}

fn filesystem_context(filesystem: &CStr) -> Result<LinuxFd, SyscallError> {
    LinuxFd::from_result(unsafe {
        abi::invoke(
            FSOPEN,
            [filesystem.as_ptr() as usize, FSOPEN_CLOEXEC, 0, 0, 0, 0],
        )
    })
}

fn filesystem_option(context: &LinuxFd, name: &CStr, value: &CStr) -> Result<(), SyscallError> {
    decode_zero(unsafe {
        abi::invoke(
            FSCONFIG,
            [
                context.as_raw_fd() as usize,
                FSCONFIG_SET_STRING,
                name.as_ptr() as usize,
                value.as_ptr() as usize,
                0,
                0,
            ],
        )
    })
}

fn create_detached_filesystem(
    context: &LinuxFd,
    mount_attributes: usize,
) -> Result<LinuxFd, SyscallError> {
    let fd = context.as_raw_fd() as usize;
    decode_zero(unsafe { abi::invoke(FSCONFIG, [fd, FSCONFIG_CMD_CREATE, 0, 0, 0, 0]) })?;
    LinuxFd::from_result(unsafe {
        abi::invoke(FSMOUNT, [fd, FSMOUNT_CLOEXEC, mount_attributes, 0, 0, 0])
    })
}

/// Create a detached procfs root for trusted task lookups.
pub(super) fn detached_proc_mount() -> Result<LinuxFd, SyscallError> {
    create_detached_filesystem(&filesystem_context(c"proc")?, NOSUID_NODEV_NOEXEC)
}

/// Create a fresh detached devpts, with its private ptmx node accessible.
pub(super) fn detached_devpts_mount() -> Result<LinuxFd, SyscallError> {
    let context = filesystem_context(c"devpts")?;
    filesystem_option(&context, c"ptmxmode", c"0600")?;
    filesystem_option(&context, c"mode", c"0600")?;
    const NOSUID_NOEXEC: usize = 2 | 8;
    create_detached_filesystem(&context, NOSUID_NOEXEC)
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum UnmountTmpfsError {
    AlreadyDetached,
    RecoveryRequired,
    SaveDirectory(SyscallError),
    EnterMount(SyscallError),
    Detach(SyscallError),
    RestoreDirectory {
        detached: bool,
        detach_error: Option<SyscallError>,
        error: SyscallError,
    },
}

impl fmt::Display for UnmountTmpfsError {
    fn fmt(&self, output: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::AlreadyDetached => output.write_str("tmpfs is already detached"),
            Self::RecoveryRequired => output.write_str("mount namespace requires external recovery"),
            Self::SaveDirectory(error) => write!(output, "could not save current directory: {error}"),
            Self::EnterMount(error) => write!(output, "could not enter the mounted root: {error}"),
            Self::Detach(error) => write!(output, "tmpfs detach failed: {error}"),
            Self::RestoreDirectory { detached, detach_error, error } => write!(
                output, "could not restore current directory: {error} (detached: {detached}, detach error: {detach_error:?})"
            ),
        }
    }
}

impl std::error::Error for UnmountTmpfsError {}

fn change_directory(fd: &LinuxFd) -> Result<(), SyscallError> {
    decode_zero(unsafe { abi::invoke(FCHDIR, [fd.as_raw_fd() as usize, 0, 0, 0, 0, 0]) })
}

/// Detaches this exact mount and restores the calling thread's saved cwd.
/// Existing opens into the tmpfs can keep the detached filesystem alive.
/// A restoration failure poisons further operations through this token.
pub fn umount2_tmpfs(mount: &mut MountedTmpfs<'_>) -> Result<(), UnmountTmpfsError> {
    if !mount.namespace.usable {
        return Err(UnmountTmpfsError::RecoveryRequired);
    }
    let root = mount
        .root
        .as_ref()
        .ok_or(UnmountTmpfsError::AlreadyDetached)?;
    let saved = save_directory().map_err(UnmountTmpfsError::SaveDirectory)?;
    change_directory(root).map_err(UnmountTmpfsError::EnterMount)?;
    let detached = decode_zero(unsafe {
        abi::invoke(UMOUNT2, [c".".as_ptr() as usize, MNT_DETACH, 0, 0, 0, 0])
    });
    let restored = change_directory(&saved);
    if detached.is_ok() {
        mount.root.take();
    }
    if let Err(error) = restored {
        mount.namespace.usable = false;
        return Err(UnmountTmpfsError::RestoreDirectory {
            detached: detached.is_ok(),
            detach_error: detached.err(),
            error,
        });
    }
    detached.map_err(UnmountTmpfsError::Detach)
}

impl Drop for MountedTmpfs<'_> {
    fn drop(&mut self) {
        if self.root.is_some() && self.namespace.usable && umount2_tmpfs(self).is_err() {
            self.namespace.usable = false;
        }
    }
}

pub(super) fn owned_mount_root<'open>(
    mount: &'open MountedTmpfs<'_>,
) -> Result<&'open LinuxFd, SyscallError> {
    if !mount.namespace.usable {
        return Err(SyscallError::InvalidInput(
            "mount namespace requires external recovery",
        ));
    }
    mount
        .root
        .as_ref()
        .ok_or(SyscallError::InvalidInput("tmpfs is already detached"))
}

/// Clone only the owned tmpfs root into a detached, close-on-exec mount FD.
/// The clone shares the existing superblock and survives detaching the source.
pub fn open_tree(mount: &MountedTmpfs<'_>) -> Result<LinuxFd, SyscallError> {
    let root = owned_mount_root(mount)?;
    LinuxFd::from_result(unsafe {
        abi::invoke(
            OPEN_TREE,
            [
                root.as_raw_fd() as usize,
                c"".as_ptr() as usize,
                OPEN_TREE_CLONE | O_CLOEXEC as usize | AT_EMPTY_PATH as usize,
                0,
                0,
                0,
            ],
        )
    })
}

/// Open a close-on-exec configuration context for the owned tmpfs.
/// This call does not issue a filesystem reconfiguration.
pub fn fspick(mount: &MountedTmpfs<'_>) -> Result<LinuxFd, SyscallError> {
    let root = owned_mount_root(mount)?;
    LinuxFd::from_result(unsafe {
        abi::invoke(
            FSPICK,
            [
                root.as_raw_fd() as usize,
                c"".as_ptr() as usize,
                FSPICK_CLOEXEC | FSPICK_EMPTY_PATH,
                0,
                0,
                0,
            ],
        )
    })
}

#[repr(C)]
struct MountAttributes {
    set: u64,
    clear: u64,
    propagation: u64,
    user_namespace: u64,
}

const _: () = {
    assert!(std::mem::size_of::<MountAttributes>() == 32);
    assert!(std::mem::align_of::<MountAttributes>() == 8);
};

/// Tighten only the owned attachment to read-only and no symlink following.
/// Existing restriction bits remain set. No propagation or ID mapping changes.
pub fn mount_setattr(mount: &MountedTmpfs<'_>) -> Result<(), SyscallError> {
    let root = owned_mount_root(mount)?;
    let attributes = MountAttributes {
        set: MOUNT_ATTR_RDONLY | MOUNT_ATTR_NOSYMFOLLOW,
        clear: 0,
        propagation: 0,
        user_namespace: 0,
    };
    decode_zero(unsafe {
        abi::invoke(
            MOUNT_SETATTR,
            [
                root.as_raw_fd() as usize,
                c"".as_ptr() as usize,
                AT_EMPTY_PATH as usize,
                std::ptr::from_ref(&attributes) as usize,
                std::mem::size_of::<MountAttributes>(),
                0,
            ],
        )
    })
}

const OLD_ROOT_DIRECTORY: &std::ffi::CStr = c".llmlang-old-root";

fn save_directory() -> Result<LinuxFd, SyscallError> {
    openat(
        Directory::Current,
        c".",
        OpenOptions {
            flags: O_PATH | O_DIRECTORY | O_CLOEXEC,
            mode: 0,
        },
    )
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ChangeRootError {
    Unavailable(SyscallError),
    OpenOldRootDirectory(SyscallError),
    SaveDirectory(SyscallError),
    EnterMount(SyscallError),
    ChangeRoot(SyscallError),
    RestoreDirectory {
        change_error: SyscallError,
        error: SyscallError,
    },
}

impl fmt::Display for ChangeRootError {
    fn fmt(&self, output: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Unavailable(error) => write!(output, "owned root is unavailable: {error}"),
            Self::OpenOldRootDirectory(error) => {
                write!(output, "cannot open old-root directory: {error}")
            }
            Self::SaveDirectory(error) => {
                write!(output, "cannot save the current directory: {error}")
            }
            Self::EnterMount(error) => write!(output, "cannot enter the owned root: {error}"),
            Self::ChangeRoot(error) => write!(output, "root switch failed: {error}"),
            Self::RestoreDirectory {
                change_error,
                error,
            } => {
                write!(output, "root switch failed: {change_error}. Directory restoration also failed: {error}")
            }
        }
    }
}

impl std::error::Error for ChangeRootError {}

enum RootChange {
    Chroot,
    Pivot,
}

fn change_root(mount: &mut MountedTmpfs<'_>, operation: RootChange) -> Result<(), ChangeRootError> {
    let root = owned_mount_root(mount).map_err(ChangeRootError::Unavailable)?;
    let _old_root = match operation {
        RootChange::Chroot => None,
        RootChange::Pivot => Some(
            openat(
                Directory::Borrowed(root.as_fd()),
                OLD_ROOT_DIRECTORY,
                OpenOptions {
                    flags: O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC,
                    mode: 0,
                },
            )
            .map_err(ChangeRootError::OpenOldRootDirectory)?,
        ),
    };
    let saved = save_directory().map_err(ChangeRootError::SaveDirectory)?;
    change_directory(root).map_err(ChangeRootError::EnterMount)?;
    let current = c".".as_ptr() as usize;
    let changed = decode_zero(unsafe {
        match operation {
            RootChange::Chroot => abi::invoke(CHROOT, [current, 0, 0, 0, 0, 0]),
            RootChange::Pivot => abi::invoke(
                PIVOT_ROOT,
                [current, OLD_ROOT_DIRECTORY.as_ptr() as usize, 0, 0, 0, 0],
            ),
        }
    });
    match changed {
        Ok(()) => {
            mount.namespace.usable = false;
            mount.root.take();
            Ok(())
        }
        Err(change_error) => match change_directory(&saved) {
            Ok(()) => Err(ChangeRootError::ChangeRoot(change_error)),
            Err(error) => {
                mount.namespace.usable = false;
                Err(ChangeRootError::RestoreDirectory {
                    change_error,
                    error,
                })
            }
        },
    }
}

/// Change the calling private filesystem context's root and cwd to the owned tmpfs.
/// Success consumes this provider's mount authority and leaves the tmpfs attached.
/// Existing descriptors remain valid. This operation alone does not isolate access.
pub fn chroot_tmpfs(mount: &mut MountedTmpfs<'_>) -> Result<(), ChangeRootError> {
    change_root(mount, RootChange::Chroot)
}

/// Pivot to the owned live tmpfs and leave the former root mounted at
/// `/.llmlang-old-root`. That directory must already exist directly beneath
/// the new root, be stable for the call and not be a symlink or another mount.
/// The caller's root must already be an attached mount in this private namespace.
/// Success consumes this provider's mount authority and does not unmount the former root.
pub fn pivot_root_tmpfs(mount: &mut MountedTmpfs<'_>) -> Result<(), ChangeRootError> {
    change_root(mount, RootChange::Pivot)
}
