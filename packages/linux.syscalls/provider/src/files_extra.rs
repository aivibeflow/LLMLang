use super::{
    abi, decode_write, decode_zero, Directory, LinuxFd, SyscallError,
};
use std::ffi::CStr;
use std::os::fd::{AsRawFd, BorrowedFd};

const STAT: usize = 4;
const FSTAT: usize = 5;
const LSTAT: usize = 6;
const ACCESS: usize = 21;
const TRUNCATE: usize = 76;
const RENAME: usize = 82;
const MKDIR: usize = 83;
const RMDIR: usize = 84;
const CREAT: usize = 85;
const LINK: usize = 86;
const UNLINK: usize = 87;
const SYMLINK: usize = 88;
const READLINK: usize = 89;
const CHMOD: usize = 90;
const NEWFSTATAT: usize = 262;
const FACCESSAT: usize = 269;

/// Creates or truncates a file and opens it for writing. Native creat leaves CLOEXEC clear.
pub fn creat(path: &CStr, mode: u16) -> Result<LinuxFd, SyscallError> {
    LinuxFd::from_result(unsafe {
        abi::invoke(CREAT, [path.as_ptr() as usize, mode as usize, 0, 0, 0, 0])
    })
}

pub fn mkdir(path: &CStr, mode: u16) -> Result<(), SyscallError> {
    path_call(MKDIR, path, mode as usize)
}

pub fn rmdir(path: &CStr) -> Result<(), SyscallError> {
    path_call(RMDIR, path, 0)
}

/// Creates a hard link. Linux does not follow the final component of `old_path`.
pub fn link(old_path: &CStr, new_path: &CStr) -> Result<(), SyscallError> {
    two_path_call(LINK, old_path, new_path)
}

pub fn unlink(path: &CStr) -> Result<(), SyscallError> {
    path_call(UNLINK, path, 0)
}

pub fn rename(old_path: &CStr, new_path: &CStr) -> Result<(), SyscallError> {
    two_path_call(RENAME, old_path, new_path)
}

pub fn symlink(target: &CStr, link_path: &CStr) -> Result<(), SyscallError> {
    two_path_call(SYMLINK, target, link_path)
}

/// Reads at most `buffer.len()` link target bytes. Linux does not append NUL.
pub fn readlink(path: &CStr, buffer: &mut [u8]) -> Result<usize, SyscallError> {
    let len = buffer.len();
    let capacity = i32::try_from(len)
        .map_err(|_| SyscallError::InvalidInput("readlink capacity exceeds Linux int"))?;
    let raw = unsafe {
        abi::invoke(
            READLINK,
            [
                path.as_ptr() as usize,
                buffer.as_mut_ptr() as usize,
                capacity as usize,
                0,
                0,
                0,
            ],
        )
    };
    decode_write(raw, len)
}

pub fn chmod(path: &CStr, mode: u16) -> Result<(), SyscallError> {
    path_call(CHMOD, path, mode as usize)
}

/// Checks access with Linux's real-ID rules for this single operation.
pub fn access(path: &CStr, mode: i32) -> Result<(), SyscallError> {
    path_call(ACCESS, path, mode as usize)
}

/// Checks access relative to a directory using the three-argument Linux ABI.
pub fn faccessat(dir: Directory<'_>, path: &CStr, mode: i32) -> Result<(), SyscallError> {
    decode_zero(unsafe {
        abi::invoke(
            FACCESSAT,
            [
                dir.argument(),
                path.as_ptr() as usize,
                mode as usize,
                0,
                0,
                0,
            ],
        )
    })
}

pub fn truncate(path: &CStr, length: i64) -> Result<(), SyscallError> {
    path_call(TRUNCATE, path, length as usize)
}

fn path_call(number: usize, path: &CStr, second: usize) -> Result<(), SyscallError> {
    decode_zero(unsafe { abi::invoke(number, [path.as_ptr() as usize, second, 0, 0, 0, 0]) })
}

fn two_path_call(number: usize, first: &CStr, second: &CStr) -> Result<(), SyscallError> {
    decode_zero(unsafe {
        abi::invoke(
            number,
            [
                first.as_ptr() as usize,
                second.as_ptr() as usize,
                0,
                0,
                0,
                0,
            ],
        )
    })
}

// Linux v6.12 arch/x86/include/uapi/asm/stat.h, native x86-64 (LP64) branch.
#[repr(C)]
#[derive(Default)]
struct NativeStat {
    device: u64,
    inode: u64,
    links: u64,
    mode: u32,
    uid: u32,
    gid: u32,
    padding: u32,
    special_device: u64,
    size: i64,
    block_size: i64,
    blocks: i64,
    access_seconds: u64,
    access_nanos: u64,
    modify_seconds: u64,
    modify_nanos: u64,
    change_seconds: u64,
    change_nanos: u64,
    reserved: [i64; 3],
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct StatTimestamp {
    seconds: i64,
    nanos: u32,
}

impl StatTimestamp {
    pub fn seconds(self) -> i64 {
        self.seconds
    }

    pub fn nanos(self) -> u32 {
        self.nanos
    }

    fn from_native(seconds: u64, nanos: u64) -> Result<Self, SyscallError> {
        if nanos >= 1_000_000_000 {
            return Err(SyscallError::UnexpectedReturn(0));
        }
        Ok(Self {
            seconds: seconds as i64,
            nanos: nanos as u32,
        })
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct FileStat {
    pub device: u64,
    pub inode: u64,
    pub links: u64,
    pub mode: u32,
    pub uid: u32,
    pub gid: u32,
    pub special_device: u64,
    pub size: i64,
    pub block_size: i64,
    pub blocks: i64,
    pub accessed: StatTimestamp,
    pub modified: StatTimestamp,
    pub changed: StatTimestamp,
}

/// Observes metadata of the resolved path and follows a final symbolic link.
pub fn stat(path: &CStr) -> Result<FileStat, SyscallError> {
    stat_path_call(STAT, path)
}

/// Observes metadata without following a final symbolic link.
pub fn lstat(path: &CStr) -> Result<FileStat, SyscallError> {
    stat_path_call(LSTAT, path)
}

pub fn fstat(fd: BorrowedFd<'_>) -> Result<FileStat, SyscallError> {
    let mut result = NativeStat::default();
    let raw = unsafe {
        abi::invoke(
            FSTAT,
            [
                fd.as_raw_fd() as usize,
                (&mut result as *mut NativeStat) as usize,
                0,
                0,
                0,
                0,
            ],
        )
    };
    stat_result(raw, result)
}

/// Observes metadata relative to a directory using the native `newfstatat` ABI.
pub fn newfstatat(dir: Directory<'_>, path: &CStr, flags: i32) -> Result<FileStat, SyscallError> {
    let mut result = NativeStat::default();
    let raw = unsafe {
        abi::invoke(
            NEWFSTATAT,
            [
                dir.argument(),
                path.as_ptr() as usize,
                (&mut result as *mut NativeStat) as usize,
                flags as usize,
                0,
                0,
            ],
        )
    };
    stat_result(raw, result)
}

fn stat_path_call(number: usize, path: &CStr) -> Result<FileStat, SyscallError> {
    let mut result = NativeStat::default();
    let raw = unsafe {
        abi::invoke(
            number,
            [
                path.as_ptr() as usize,
                (&mut result as *mut NativeStat) as usize,
                0,
                0,
                0,
                0,
            ],
        )
    };
    stat_result(raw, result)
}

fn stat_result(raw: isize, result: NativeStat) -> Result<FileStat, SyscallError> {
    decode_zero(raw)?;
    Ok(FileStat {
        device: result.device,
        inode: result.inode,
        links: result.links,
        mode: result.mode,
        uid: result.uid,
        gid: result.gid,
        special_device: result.special_device,
        size: result.size,
        block_size: result.block_size,
        blocks: result.blocks,
        accessed: StatTimestamp::from_native(result.access_seconds, result.access_nanos)?,
        modified: StatTimestamp::from_native(result.modify_seconds, result.modify_nanos)?,
        changed: StatTimestamp::from_native(result.change_seconds, result.change_nanos)?,
    })
}

#[cfg(test)]
mod layout_tests {
    use super::*;
    use std::mem::{align_of, offset_of, size_of};

    #[test]
    fn native_stat_layout_matches_x86_64_abi() {
        assert_eq!(size_of::<NativeStat>(), 144);
        assert_eq!(align_of::<NativeStat>(), 8);
        assert_eq!(offset_of!(NativeStat, mode), 24);
        assert_eq!(offset_of!(NativeStat, special_device), 40);
        assert_eq!(offset_of!(NativeStat, size), 48);
        assert_eq!(offset_of!(NativeStat, access_seconds), 72);
        assert_eq!(offset_of!(NativeStat, change_nanos), 112);
        assert_eq!(offset_of!(NativeStat, reserved), 120);
        assert_eq!(
            StatTimestamp::from_native(u64::MAX, 999_999_999)
                .unwrap()
                .seconds(),
            -1
        );
        assert!(StatTimestamp::from_native(0, 1_000_000_000).is_err());
    }
}
