//! Read-only Linux system observations and random bytes.
use std::ffi::CStr;
use std::os::raw::c_char;

use crate::abi::invoke;
use crate::{decode_nonnegative, decode_write, decode_zero, SyscallError};

const UNAME: usize = 63;
const SYSINFO: usize = 99;
pub(super) const GETUID: usize = 102;
const GETGID: usize = 104;
const GETEUID: usize = 107;
const GETEGID: usize = 108;
const GETPPID: usize = 110;
const GETRANDOM: usize = 318;

#[derive(Debug)]
#[repr(C)]
pub struct UtsName {
    system: [c_char; 65],
    node: [c_char; 65],
    release: [c_char; 65],
    version: [c_char; 65],
    machine: [c_char; 65],
    domain: [c_char; 65],
}

impl UtsName {
    pub fn system(&self) -> &CStr {
        // The constructor verifies a terminator inside each field.
        unsafe { CStr::from_ptr(self.system.as_ptr()) }
    }

    pub fn node(&self) -> &CStr {
        unsafe { CStr::from_ptr(self.node.as_ptr()) }
    }

    pub fn release(&self) -> &CStr {
        unsafe { CStr::from_ptr(self.release.as_ptr()) }
    }

    pub fn version(&self) -> &CStr {
        unsafe { CStr::from_ptr(self.version.as_ptr()) }
    }

    pub fn machine(&self) -> &CStr {
        unsafe { CStr::from_ptr(self.machine.as_ptr()) }
    }

    pub fn domain(&self) -> &CStr {
        unsafe { CStr::from_ptr(self.domain.as_ptr()) }
    }
}

pub fn uname() -> Result<UtsName, SyscallError> {
    let mut value = UtsName {
        system: [0; 65],
        node: [0; 65],
        release: [0; 65],
        version: [0; 65],
        machine: [0; 65],
        domain: [0; 65],
    };
    // Linux x86-64 writes one struct new_utsname.
    decode_zero(unsafe { invoke(UNAME, [&mut value as *mut UtsName as usize, 0, 0, 0, 0, 0]) })?;
    if [
        &value.system,
        &value.node,
        &value.release,
        &value.version,
        &value.machine,
        &value.domain,
    ]
    .iter()
    .any(|field| !field.contains(&0))
    {
        return Err(SyscallError::InvalidInput(
            "uname returned an unterminated field",
        ));
    }
    Ok(value)
}

#[derive(Debug, Default, Copy, Clone)]
#[repr(C)]
pub struct SystemInfo {
    pub uptime: i64,
    pub loads: [u64; 3],
    pub total_ram: u64,
    pub free_ram: u64,
    pub shared_ram: u64,
    pub buffer_ram: u64,
    pub total_swap: u64,
    pub free_swap: u64,
    pub processes: u16,
    padding: [u8; 6],
    pub total_high: u64,
    pub free_high: u64,
    pub memory_unit: u32,
    trailing_padding: [u8; 4],
}

const _: () = {
    assert!(std::mem::size_of::<UtsName>() == 390);
    assert!(std::mem::align_of::<UtsName>() == 1);
    assert!(std::mem::offset_of!(UtsName, domain) == 325);
    assert!(std::mem::size_of::<SystemInfo>() == 112);
    assert!(std::mem::align_of::<SystemInfo>() == 8);
    assert!(std::mem::offset_of!(SystemInfo, processes) == 80);
    assert!(std::mem::offset_of!(SystemInfo, total_high) == 88);
    assert!(std::mem::offset_of!(SystemInfo, memory_unit) == 104);
};

pub fn sysinfo() -> Result<SystemInfo, SyscallError> {
    let mut value = SystemInfo::default();
    // Linux x86-64 writes one struct sysinfo.
    decode_zero(unsafe {
        invoke(
            SYSINFO,
            [&mut value as *mut SystemInfo as usize, 0, 0, 0, 0, 0],
        )
    })?;
    Ok(value)
}

#[derive(Copy, Clone, Debug, Eq, PartialEq)]
#[repr(u32)]
pub enum RandomMode {
    Blocking = 0,
    Nonblocking = 1,
}

pub fn getrandom(buffer: &mut [u8], mode: RandomMode) -> Result<usize, SyscallError> {
    let raw = unsafe {
        invoke(
            GETRANDOM,
            [
                buffer.as_mut_ptr() as usize,
                buffer.len(),
                mode as usize,
                0,
                0,
                0,
            ],
        )
    };
    decode_write(raw, buffer.len())
}

fn id(number: usize) -> Result<u32, SyscallError> {
    // Each caller selects a nullary identifier query.
    let raw = unsafe { invoke(number, [0; 6]) };
    u32::try_from(decode_nonnegative(raw)?).map_err(|_| SyscallError::UnexpectedReturn(raw))
}

pub fn getppid() -> Result<i32, SyscallError> {
    i32::try_from(id(GETPPID)?).map_err(|_| SyscallError::InvalidInput("invalid parent process ID"))
}

pub fn getuid() -> Result<u32, SyscallError> {
    id(GETUID)
}

pub fn getgid() -> Result<u32, SyscallError> {
    id(GETGID)
}

pub fn geteuid() -> Result<u32, SyscallError> {
    id(GETEUID)
}

pub fn getegid() -> Result<u32, SyscallError> {
    id(GETEGID)
}
