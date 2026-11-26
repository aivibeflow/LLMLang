use super::{abi, decode_nonnegative, decode_zero, LinuxFd, SyscallError};
use std::mem::{align_of, offset_of, size_of};
use std::os::fd::{AsFd, AsRawFd, BorrowedFd};

const LANDLOCK_CREATE_RULESET: usize = 444;
const LANDLOCK_ADD_RULE: usize = 445;
const LANDLOCK_RESTRICT_SELF: usize = 446;
const LANDLOCK_CREATE_RULESET_VERSION: usize = 1;
const LANDLOCK_RULE_PATH_BENEATH: usize = 1;
const LANDLOCK_ACCESS_FS_READ_FILE: u64 = 1 << 2;
const LANDLOCK_ACCESS_FS_READ_DIR: u64 = 1 << 3;

#[repr(C)]
struct RulesetFsV1 {
    handled_access_fs: u64,
}

#[repr(C, packed)]
struct PathBeneathRule {
    allowed_access: u64,
    parent_fd: i32,
}

const _: () = {
    assert!(size_of::<RulesetFsV1>() == 8);
    assert!(align_of::<RulesetFsV1>() == 8);
    assert!(size_of::<PathBeneathRule>() == 12);
    assert!(align_of::<PathBeneathRule>() == 1);
    assert!(offset_of!(PathBeneathRule, parent_fd) == 8);
};

/// Owns one Landlock ruleset descriptor. Closing it releases the ruleset
/// object when the kernel no longer needs it. Applied restrictions persist.
#[derive(Debug)]
pub struct LandlockRuleset(LinuxFd);

impl LandlockRuleset {
    pub fn into_fd(self) -> LinuxFd {
        self.0
    }
}

impl AsFd for LandlockRuleset {
    fn as_fd(&self) -> BorrowedFd<'_> {
        self.0.borrow()
    }
}

#[repr(u64)]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum LandlockReadAccess {
    Files = LANDLOCK_ACCESS_FS_READ_FILE,
    Directories = LANDLOCK_ACCESS_FS_READ_DIR,
    FilesAndDirectories = LANDLOCK_ACCESS_FS_READ_FILE | LANDLOCK_ACCESS_FS_READ_DIR,
}

/// Query the highest advertised Landlock ABI. This observation does not
/// select a provider automatically or install a policy.
pub fn landlock_create_ruleset_version() -> Result<u32, SyscallError> {
    let raw = unsafe {
        abi::invoke(
            LANDLOCK_CREATE_RULESET,
            [0, 0, LANDLOCK_CREATE_RULESET_VERSION, 0, 0, 0],
        )
    };
    let version = decode_nonnegative(raw)?;
    if version == 0 {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    u32::try_from(version).map_err(|_| SyscallError::UnexpectedReturn(raw))
}

/// Creates a ruleset for new file-read and directory-read opens. The
/// original ABI-1 filesystem field is the whole supplied structure.
pub fn landlock_create_ruleset() -> Result<LandlockRuleset, SyscallError> {
    let attributes = RulesetFsV1 {
        handled_access_fs: LANDLOCK_ACCESS_FS_READ_FILE | LANDLOCK_ACCESS_FS_READ_DIR,
    };
    let raw = unsafe {
        abi::invoke(
            LANDLOCK_CREATE_RULESET,
            [
                (&attributes as *const RulesetFsV1) as usize,
                size_of::<RulesetFsV1>(),
                0,
                0,
                0,
                0,
            ],
        )
    };
    Ok(LandlockRuleset(LinuxFd::from_result(raw)?))
}

/// Adds the selected read rights for the filesystem object and its
/// applicable descendants. The parent descriptor remains borrowed.
pub fn landlock_add_rule(
    ruleset: &mut LandlockRuleset,
    parent: BorrowedFd<'_>,
    allowed: LandlockReadAccess,
) -> Result<(), SyscallError> {
    let attributes = PathBeneathRule {
        allowed_access: allowed as u64,
        parent_fd: parent.as_raw_fd(),
    };
    decode_zero(unsafe {
        abi::invoke(
            LANDLOCK_ADD_RULE,
            [
                ruleset.as_fd().as_raw_fd() as usize,
                LANDLOCK_RULE_PATH_BENEATH,
                (&attributes as *const PathBeneathRule) as usize,
                0,
                0,
                0,
            ],
        )
    })
}

/// Applies an additional restriction to the calling thread and its future
/// descendants. Linux requires no_new_privs or the ambient user namespace
/// capability. The ruleset cannot relax restrictions that are already in
/// force. This call does not set no_new_privs or affect existing threads.
pub fn landlock_restrict_self(ruleset: &LandlockRuleset) -> Result<(), SyscallError> {
    decode_zero(unsafe {
        abi::invoke(
            LANDLOCK_RESTRICT_SELF,
            [ruleset.as_fd().as_raw_fd() as usize, 0, 0, 0, 0, 0],
        )
    })
}
