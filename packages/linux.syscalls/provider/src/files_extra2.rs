use super::{abi, decode_write, decode_zero, LinuxFd, SyscallError};
use std::ffi::CStr;
use std::os::fd::{AsRawFd, BorrowedFd};

const SENDFILE: usize = 40;
const STATFS: usize = 137;
const FSTATFS: usize = 138;
const MEMFD_CREATE: usize = 319;
const MFD_CLOEXEC: usize = 0x0001;

// Linux v6.12 arch/x86/include/uapi/asm/statfs.h and asm-generic/statfs.h.
// The native LP64 struct uses kernel long and a two-word filesystem ID.
#[repr(C)]
#[derive(Default)]
struct NativeStatfs {
    fs_type: i64,
    block_size: i64,
    blocks: i64,
    blocks_free: i64,
    blocks_available: i64,
    files: i64,
    files_free: i64,
    filesystem_id: [i32; 2],
    name_length: i64,
    fragment_size: i64,
    flags: i64,
    reserved: [i64; 4],
}

/// An observation of a filesystem. Linux filesystems may report an all-ones
/// count for an unavailable property. Counts and flags retain their raw bits.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct FileSystemStat {
    pub fs_type: i64,
    pub block_size: i64,
    pub blocks: u64,
    pub blocks_free: u64,
    pub blocks_available: u64,
    pub files: u64,
    pub files_free: u64,
    pub filesystem_id: [i32; 2],
    pub name_length: i64,
    pub fragment_size: i64,
    pub flags: u64,
}

pub fn statfs(path: &CStr) -> Result<FileSystemStat, SyscallError> {
    observe_statfs(STATFS, path.as_ptr() as usize)
}

pub fn fstatfs(fd: BorrowedFd<'_>) -> Result<FileSystemStat, SyscallError> {
    observe_statfs(FSTATFS, fd.as_raw_fd() as usize)
}

fn observe_statfs(number: usize, subject: usize) -> Result<FileSystemStat, SyscallError> {
    let mut result = NativeStatfs::default();
    let raw = unsafe {
        abi::invoke(
            number,
            [
                subject,
                (&mut result as *mut NativeStatfs) as usize,
                0,
                0,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)?;
    Ok(FileSystemStat {
        fs_type: result.fs_type,
        block_size: result.block_size,
        blocks: result.blocks as u64,
        blocks_free: result.blocks_free as u64,
        blocks_available: result.blocks_available as u64,
        files: result.files as u64,
        files_free: result.files_free as u64,
        filesystem_id: result.filesystem_id,
        name_length: result.name_length,
        fragment_size: result.fragment_size,
        flags: result.flags as u64,
    })
}

/// Transfers up to `count` bytes using native x86-64 sendfile64. An explicit
/// input offset advances by actual progress, while the input descriptor's
/// cursor stays unchanged. `None` instead delegates input position to Linux.
/// The output cursor, where applicable, advances by kernel progress.
pub fn sendfile(
    output: BorrowedFd<'_>,
    input: BorrowedFd<'_>,
    input_offset: Option<&mut i64>,
    count: usize,
) -> Result<usize, SyscallError> {
    let original = input_offset.as_deref().copied();
    let mut observed = original;
    let offset = observed
        .as_mut()
        .map_or(0, |value| value as *mut i64 as usize);
    let raw = unsafe {
        abi::invoke(
            SENDFILE,
            [
                output.as_raw_fd() as usize,
                input.as_raw_fd() as usize,
                offset,
                count,
                0,
                0,
            ],
        )
    };
    let progress = decode_write(raw, count)?;
    if let Some(position) = input_offset {
        let expected = position
            .checked_add(progress as i64)
            .ok_or(SyscallError::UnexpectedReturn(raw))?;
        if observed != Some(expected) {
            return Err(SyscallError::UnexpectedReturn(raw));
        }
        *position = expected;
    }
    Ok(progress)
}

/// Creates a new zero-length anonymous file. CLOEXEC is set atomically.
/// The supplied name labels the file and does not look up another descriptor.
pub fn memfd_create(name: &CStr) -> Result<LinuxFd, SyscallError> {
    memfd_create_with_flags(name, 0)
}

pub(super) fn memfd_create_with_flags(name: &CStr, flags: usize) -> Result<LinuxFd, SyscallError> {
    let raw = unsafe {
        abi::invoke(
            MEMFD_CREATE,
            [name.as_ptr() as usize, MFD_CLOEXEC | flags, 0, 0, 0, 0],
        )
    };
    LinuxFd::from_result(raw)
}

#[cfg(test)]
mod layout_tests {
    use super::*;
    use std::mem::{align_of, offset_of, size_of};

    #[test]
    fn native_statfs_layout_matches_x86_64_abi() {
        assert_eq!(size_of::<NativeStatfs>(), 120);
        assert_eq!(align_of::<NativeStatfs>(), 8);
        assert_eq!(offset_of!(NativeStatfs, blocks_available), 32);
        assert_eq!(offset_of!(NativeStatfs, filesystem_id), 56);
        assert_eq!(offset_of!(NativeStatfs, name_length), 64);
        assert_eq!(offset_of!(NativeStatfs, fragment_size), 72);
        assert_eq!(offset_of!(NativeStatfs, flags), 80);
        assert_eq!(offset_of!(NativeStatfs, reserved), 88);
    }
}
