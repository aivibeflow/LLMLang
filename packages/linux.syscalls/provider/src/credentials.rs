//! Read-only observations of the caller's Linux credentials.
use crate::{abi, decode_nonnegative, decode_zero, SyscallError};

const GETRESUID: usize = 118;
const GETRESGID: usize = 120;
const SETFSUID: usize = 122;
const SETFSGID: usize = 123;
const CAPGET: usize = 125;
const CAPSET: usize = 126;
const CAPABILITY_VERSION_3: u32 = 0x2008_0522;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CredentialIds {
    pub real: u32,
    pub effective: u32,
    pub saved: u32,
}

fn credential_ids(number: usize) -> Result<CredentialIds, SyscallError> {
    let mut ids = CredentialIds {
        real: 0,
        effective: 0,
        saved: 0,
    };
    let raw = unsafe {
        abi::call(
            number,
            [
                std::ptr::from_mut(&mut ids.real) as usize,
                std::ptr::from_mut(&mut ids.effective) as usize,
                std::ptr::from_mut(&mut ids.saved) as usize,
                0,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)?;
    Ok(ids)
}

pub fn getresuid() -> Result<CredentialIds, SyscallError> {
    credential_ids(GETRESUID)
}

pub fn getresgid() -> Result<CredentialIds, SyscallError> {
    credential_ids(GETRESGID)
}

fn filesystem_id(number: usize) -> Result<u32, SyscallError> {
    // Linux represents an invalid (unmapped) UID or GID using all ones.
    // The v6.12 syscall returns the current unsigned filesystem ID unchanged.
    let raw = unsafe { abi::call(number, [u32::MAX as usize, 0, 0, 0, 0, 0]) };
    u32::try_from(decode_nonnegative(raw)?).map_err(|_| SyscallError::UnexpectedReturn(raw))
}

pub fn setfsuid_query() -> Result<u32, SyscallError> {
    filesystem_id(SETFSUID)
}

pub fn setfsgid_query() -> Result<u32, SyscallError> {
    filesystem_id(SETFSGID)
}

#[repr(C)]
struct CapabilityHeader {
    version: u32,
    pid: i32,
}

#[repr(C)]
#[derive(Clone, Copy, Default)]
struct CapabilityWord {
    effective: u32,
    permitted: u32,
    inheritable: u32,
}

const _: () = {
    assert!(std::mem::size_of::<CapabilityHeader>() == 8);
    assert!(std::mem::size_of::<CapabilityWord>() == 12);
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CapabilitySets {
    pub effective: u64,
    pub permitted: u64,
    pub inheritable: u64,
}

pub fn capget() -> Result<CapabilitySets, SyscallError> {
    let mut header = CapabilityHeader {
        version: CAPABILITY_VERSION_3,
        pid: 0,
    };
    let mut words = [CapabilityWord::default(); 2];
    let raw = unsafe {
        abi::call(
            CAPGET,
            [
                std::ptr::from_mut(&mut header) as usize,
                words.as_mut_ptr() as usize,
                0,
                0,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)?;
    let [low, high] = words;
    let combine = |low: u32, high: u32| u64::from(low) | (u64::from(high) << 32);
    Ok(CapabilitySets {
        effective: combine(low.effective, high.effective),
        permitted: combine(low.permitted, high.permitted),
        inheritable: combine(low.inheritable, high.inheritable),
    })
}

/// Clear all capability sets of the calling thread.
pub fn capset_clear() -> Result<(), SyscallError> {
    let mut header = CapabilityHeader {
        version: CAPABILITY_VERSION_3,
        pid: 0,
    };
    let words = [CapabilityWord::default(); 2];
    decode_zero(unsafe {
        abi::call(
            CAPSET,
            [
                std::ptr::from_mut(&mut header) as usize,
                words.as_ptr() as usize,
                0,
                0,
                0,
                0,
            ],
        )
    })
}
