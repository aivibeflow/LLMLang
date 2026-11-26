//! Fixed-size data maps for three Linux BPF commands.
use std::mem::{offset_of, size_of};
use std::os::fd::AsRawFd;

use crate::{abi, decode_zero, LinuxFd, SyscallError};

const BPF: usize = 321;
const MAP_CREATE: usize = 0;
const MAP_LOOKUP_ELEM: usize = 1;
const MAP_UPDATE_ELEM: usize = 2;
const MAP_TYPE_ARRAY: u32 = 2;
const MAX_ENTRIES: u32 = 1024;

#[repr(C)]
struct MapCreate {
    map_type: u32,
    key_size: u32,
    value_size: u32,
    max_entries: u32,
    map_flags: u32,
}

#[repr(C)]
struct MapElement {
    map_fd: u32,
    padding: u32,
    key: u64,
    value: u64,
    flags: u64,
}

const _: () = {
    assert!(size_of::<MapCreate>() == 20);
    assert!(size_of::<MapElement>() == 32);
    assert!(offset_of!(MapElement, key) == 8);
    assert!(offset_of!(MapElement, value) == 16);
    assert!(offset_of!(MapElement, flags) == 24);
};

/// Owns an array map with 32-bit indices and 64-bit values. Dropping it closes
/// the only descriptor exposed by this profile.
#[derive(Debug)]
pub struct BpfArray {
    fd: LinuxFd,
    entries: u32,
}

fn map_call<T>(command: usize, attributes: &T) -> isize {
    // This private call is used only with the command's initialized UAPI prefix.
    unsafe {
        abi::invoke(
            BPF,
            [
                command,
                std::ptr::from_ref(attributes) as usize,
                size_of::<T>(),
                0,
                0,
                0,
            ],
        )
    }
}

pub fn bpf_map_create_u64(entries: u32) -> Result<BpfArray, SyscallError> {
    if !(1..=MAX_ENTRIES).contains(&entries) {
        return Err(SyscallError::InvalidInput(
            "BPF array length must be 1 through 1024",
        ));
    }
    let attributes = MapCreate {
        map_type: MAP_TYPE_ARRAY,
        key_size: size_of::<u32>() as u32,
        value_size: size_of::<u64>() as u32,
        max_entries: entries,
        map_flags: 0,
    };
    let fd = LinuxFd::from_result(map_call(MAP_CREATE, &attributes))?;
    Ok(BpfArray { fd, entries })
}

fn element(map: &BpfArray, index: &u32, value: usize) -> Result<MapElement, SyscallError> {
    if *index >= map.entries {
        return Err(SyscallError::InvalidInput("BPF array index out of bounds"));
    }
    Ok(MapElement {
        map_fd: map.fd.as_raw_fd() as u32,
        padding: 0,
        key: std::ptr::from_ref(index) as u64,
        value: value as u64,
        flags: 0,
    })
}

pub fn bpf_map_lookup_u64(map: &BpfArray, index: u32) -> Result<u64, SyscallError> {
    let mut value = 0_u64;
    let attributes = element(map, &index, std::ptr::from_mut(&mut value) as usize)?;
    decode_zero(map_call(MAP_LOOKUP_ELEM, &attributes))?;
    Ok(value)
}

pub fn bpf_map_update_u64(map: &mut BpfArray, index: u32, value: u64) -> Result<(), SyscallError> {
    let attributes = element(map, &index, std::ptr::from_ref(&value) as usize)?;
    decode_zero(map_call(MAP_UPDATE_ELEM, &attributes))
}
