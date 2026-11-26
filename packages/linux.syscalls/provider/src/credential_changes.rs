//! Native Linux credential setters operate on the calling thread. They do
//! not run the C library's process-wide credential synchronization.
use super::{abi, decode_zero, SyscallError};

const SETUID: usize = 105;
const SETGID: usize = 106;
const SETREUID: usize = 113;
const SETREGID: usize = 114;
const SETGROUPS: usize = 116;
const SETRESUID: usize = 117;
const SETRESGID: usize = 119;
const KEEP_ID: u32 = u32::MAX;
const MAX_SUPPLEMENTARY_GROUPS: usize = 65_536;

fn check_id(value: u32) -> Result<u32, SyscallError> {
    if value == KEEP_ID {
        return Err(SyscallError::InvalidInput(
            "credential ID uses the reserved no-change value",
        ));
    }
    Ok(value)
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct UserId(u32);

impl UserId {
    pub fn new(value: u32) -> Result<Self, SyscallError> {
        check_id(value).map(Self)
    }

    pub fn value(self) -> u32 {
        self.0
    }
}

#[repr(transparent)]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct GroupId(u32);

impl GroupId {
    pub fn new(value: u32) -> Result<Self, SyscallError> {
        check_id(value).map(Self)
    }

    pub fn value(self) -> u32 {
        self.0
    }
}

const _: () = {
    assert!(std::mem::size_of::<GroupId>() == 4);
    assert!(std::mem::align_of::<GroupId>() == 4);
};

fn set_ids(operation: usize, first: u32, second: u32, third: u32) -> Result<(), SyscallError> {
    let raw = unsafe {
        abi::call(
            operation,
            [first as usize, second as usize, third as usize, 0, 0, 0],
        )
    };
    decode_zero(raw)
}

/// Sets the caller's UID according to Linux privilege and saved-ID rules.
pub fn setuid(id: UserId) -> Result<(), SyscallError> {
    set_ids(SETUID, id.0, 0, 0)
}

/// Sets the caller's GID according to Linux privilege and saved-ID rules.
pub fn setgid(id: GroupId) -> Result<(), SyscallError> {
    set_ids(SETGID, id.0, 0, 0)
}

/// Requests real/effective UID updates. Linux can also update the saved and
/// filesystem UID under its native rules. None leaves that selector omitted.
pub fn setreuid(real: Option<UserId>, effective: Option<UserId>) -> Result<(), SyscallError> {
    set_ids(
        SETREUID,
        real.map_or(KEEP_ID, UserId::value),
        effective.map_or(KEEP_ID, UserId::value),
        0,
    )
}

/// Requests real/effective GID updates. Linux can also update the saved and
/// filesystem GID under its native rules. None leaves that selector omitted.
pub fn setregid(real: Option<GroupId>, effective: Option<GroupId>) -> Result<(), SyscallError> {
    set_ids(
        SETREGID,
        real.map_or(KEEP_ID, GroupId::value),
        effective.map_or(KEEP_ID, GroupId::value),
        0,
    )
}

/// Requests real/effective/saved UID updates for the calling thread.
pub fn setresuid(
    real: Option<UserId>,
    effective: Option<UserId>,
    saved: Option<UserId>,
) -> Result<(), SyscallError> {
    set_ids(
        SETRESUID,
        real.map_or(KEEP_ID, UserId::value),
        effective.map_or(KEEP_ID, UserId::value),
        saved.map_or(KEEP_ID, UserId::value),
    )
}

/// Requests real/effective/saved GID updates for the calling thread.
pub fn setresgid(
    real: Option<GroupId>,
    effective: Option<GroupId>,
    saved: Option<GroupId>,
) -> Result<(), SyscallError> {
    set_ids(
        SETRESGID,
        real.map_or(KEEP_ID, GroupId::value),
        effective.map_or(KEEP_ID, GroupId::value),
        saved.map_or(KEEP_ID, GroupId::value),
    )
}

/// Replaces only the caller's supplementary groups. An empty list requests
/// clearing the set. Linux checks namespace mappings, permission, and limits.
pub fn setgroups(groups: &[GroupId]) -> Result<(), SyscallError> {
    if groups.len() > MAX_SUPPLEMENTARY_GROUPS {
        return Err(SyscallError::InvalidInput(
            "supplementary group list exceeds Linux NGROUPS_MAX",
        ));
    }
    // GroupId is transparent over the native x86-64 gid_t, and the slice
    // remains shared and live for the kernel's complete read extent.
    let raw = unsafe {
        abi::call(
            SETGROUPS,
            [groups.len(), groups.as_ptr() as usize, 0, 0, 0, 0],
        )
    };
    decode_zero(raw)
}
