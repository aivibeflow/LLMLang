//! Observe a kernel-issued return trampoline on a fixed current-image function.
use std::ffi::{CStr, CString};
use std::hint::black_box;
use std::os::fd::{AsRawFd, BorrowedFd};

use crate::complex::perf_event_open_uprobe;
use crate::{
    fstat, fstatfs, openat, read, Directory, FileStat, LinuxFd, OpenOptions, ReadOutcome,
    SyscallError, O_RDONLY,
};

// An ABI identity used by the package binding. Only the kernel trampoline
// executes this entry, so no application call site references the constant.
#[allow(dead_code)]
const URETPROBE: usize = 335;
const PROC_SUPER_MAGIC: i64 = 0x9fa0;
const SYSFS_MAGIC: i64 = 0x6265_6572;
const PERF_FIRST_DYNAMIC_TYPE: u32 = 6;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct UretprobeObservation {
    pub result: u32,
    pub returns: u64,
}

#[inline(never)]
extern "C" fn fixed_return_fixture(input: u32) -> u32 {
    input.rotate_left(7) ^ 0x52a4_ccde
}

fn open_kernel_file(path: &CStr) -> Result<LinuxFd, SyscallError> {
    openat(
        Directory::Current,
        path,
        OpenOptions {
            flags: O_RDONLY,
            mode: 0,
        },
    )
}

fn uprobe_type() -> Result<u32, SyscallError> {
    let source = open_kernel_file(c"/sys/bus/event_source/devices/uprobe/type")?;
    if fstatfs(source.borrow())?.fs_type != SYSFS_MAGIC {
        return Err(SyscallError::InvalidInput("expected uprobe PMU sysfs file"));
    }
    let mut buffer = [0; 32];
    let ReadOutcome::Progress(count) = read(source.borrow(), &mut buffer)? else {
        return Err(SyscallError::UnexpectedReturn(0));
    };
    std::str::from_utf8(&buffer[..count])
        .ok()
        .and_then(|text| text.trim_end_matches('\n').parse().ok())
        .filter(|&event_type| event_type >= PERF_FIRST_DYNAMIC_TYPE)
        .ok_or(SyscallError::UnexpectedReturn(count as isize))
}

fn parse_hex(bytes: &[u8]) -> Option<u64> {
    u64::from_str_radix(std::str::from_utf8(bytes).ok()?, 16).ok()
}

fn split_pair(bytes: &[u8], separator: u8) -> Option<(&[u8], &[u8])> {
    let index = bytes.iter().position(|&byte| byte == separator)?;
    Some((&bytes[..index], &bytes[index + 1..]))
}

fn mapped_file_offset(line: &[u8], address: u64, exe: &FileStat) -> Option<u64> {
    let mut fields = line
        .split(|byte| byte.is_ascii_whitespace())
        .filter(|field| !field.is_empty());
    let (start, end) = split_pair(fields.next()?, b'-')?;
    let start = parse_hex(start)?;
    if !(start..parse_hex(end)?).contains(&address) || fields.next()?.get(2) != Some(&b'x') {
        return None;
    }
    let page_offset = parse_hex(fields.next()?)?;
    let (major, minor) = split_pair(fields.next()?, b':')?;
    let minor = parse_hex(minor)?;
    let device = (parse_hex(major)? << 8) | (minor & 0xff) | ((minor & !0xff) << 12);
    let inode = std::str::from_utf8(fields.next()?)
        .ok()?
        .parse::<u64>()
        .ok()?;
    if device != exe.device || inode != exe.inode {
        return None;
    }
    let offset = page_offset.checked_add(address - start)?;
    (offset < u64::try_from(exe.size).ok()?).then_some(offset)
}

fn fixture_offset(exe: &FileStat) -> Result<u64, SyscallError> {
    let maps = open_kernel_file(c"/proc/self/maps")?;
    if fstatfs(maps.borrow())?.fs_type != PROC_SUPER_MAGIC {
        return Err(SyscallError::InvalidInput(
            "expected current process maps from procfs",
        ));
    }
    let addr = fixed_return_fixture as *const () as u64;
    let mut chunk = [0; 4096];
    // A native maps record's address, offset, device and inode precede any
    // optional pathname. Keep only that prefix while streaming the records.
    let mut prefix = [0; 128];
    let mut length = 0;
    while let ReadOutcome::Progress(count) = read(maps.borrow(), &mut chunk)? {
        for &byte in &chunk[..count] {
            if byte == b'\n' {
                if let Some(offset) = mapped_file_offset(&prefix[..length], addr, exe) {
                    return Ok(offset);
                }
                length = 0;
            } else if length < prefix.len() {
                prefix[length] = byte;
                length += 1;
            }
        }
    }
    Err(SyscallError::InvalidInput(
        "fixed fixture is not mapped from the current executable",
    ))
}

fn event_count(event: BorrowedFd<'_>) -> Result<u64, SyscallError> {
    let mut bytes = [0_u8; 8];
    match read(event, &mut bytes)? {
        ReadOutcome::Progress(8) => Ok(u64::from_ne_bytes(bytes)),
        ReadOutcome::Progress(count) => Err(SyscallError::UnexpectedReturn(count as isize)),
        _ => Err(SyscallError::UnexpectedReturn(0)),
    }
}

/// Observe one return probe on a fixed provider function in the current
/// executable. Requires procfs, sysfs, and permission to open the uprobe PMU.
/// Only the kernel-created trampoline reaches the native uretprobe entry.
pub fn uretprobe(input: u32) -> Result<UretprobeObservation, SyscallError> {
    let event_type = uprobe_type()?;
    let executable = open_kernel_file(c"/proc/self/exe")?;
    let metadata = fstat(executable.borrow())?;
    let offset = fixture_offset(&metadata)?;
    let subject = CString::new(format!("/proc/self/fd/{}", executable.as_raw_fd()))
        .expect("decimal descriptor path");
    let event = perf_event_open_uprobe(event_type, &subject, offset)?;
    if event_count(event.borrow())? != 0 {
        return Err(SyscallError::UnexpectedReturn(0));
    }

    // Preserve the exact call entry even with link-time optimization.
    let invoke = black_box(fixed_return_fixture as extern "C" fn(u32) -> u32);
    let result = invoke(input);
    let returns = event_count(event.borrow())?;
    if returns != 1 || result != input.rotate_left(7) ^ 0x52a4_ccde {
        return Err(SyscallError::UnexpectedReturn(0));
    }
    Ok(UretprobeObservation { result, returns })
}
