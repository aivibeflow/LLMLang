use super::{abi, decode_write, decode_zero, Directory, SyscallError};
use std::ffi::CStr;
use std::os::fd::{AsRawFd, BorrowedFd};

const READAHEAD: usize = 187;
const FADVISE64: usize = 221;
const SYNC_FILE_RANGE: usize = 277;
const FALLOCATE: usize = 285;
const RENAMEAT2: usize = 316;
const COPY_FILE_RANGE: usize = 326;

/// Reserves space in a regular file using Linux fallocate mode 0. The file can
/// grow, while existing bytes and the open file description offset are preserved.
pub fn fallocate(fd: BorrowedFd<'_>, offset: i64, length: i64) -> Result<(), SyscallError> {
    decode_zero(unsafe {
        abi::invoke(
            FALLOCATE,
            [
                fd.as_raw_fd() as usize,
                0,
                offset as usize,
                length as usize,
                0,
                0,
            ],
        )
    })
}

#[repr(u32)]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum FileAdvice {
    Normal = 0,
    Random = 1,
    Sequential = 2,
    WillNeed = 3,
    DontNeed = 4,
    NoReuse = 5,
}

/// Passes advisory access-pattern information for a range without moving the
/// file cursor. A successful request does not attest to the cache contents.
pub fn fadvise64(
    fd: BorrowedFd<'_>,
    offset: i64,
    length: usize,
    advice: FileAdvice,
) -> Result<(), SyscallError> {
    decode_zero(unsafe {
        abi::invoke(
            FADVISE64,
            [
                fd.as_raw_fd() as usize,
                offset as usize,
                length,
                advice as usize,
                0,
                0,
            ],
        )
    })
}

/// Requests advisory readahead without advancing the file cursor. Success is
/// reported as completion of the request, without a byte count.
pub fn readahead(fd: BorrowedFd<'_>, offset: i64, length: usize) -> Result<(), SyscallError> {
    decode_zero(unsafe {
        abi::invoke(
            READAHEAD,
            [fd.as_raw_fd() as usize, offset as usize, length, 0, 0, 0],
        )
    })
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct SyncFileRangeFlags(u32);

impl SyncFileRangeFlags {
    pub const NONE: Self = Self(0);
    pub const WAIT_BEFORE: Self = Self(1);
    pub const WRITE: Self = Self(2);
    pub const WAIT_AFTER: Self = Self(4);

    pub const fn combine(self, other: Self) -> Self {
        Self(self.0 | other.0)
    }
}

/// Requests or waits for writeback of a Linux page-cache range. This interface
/// reports the selected writeback operation and gives no durability guarantee.
pub fn sync_file_range(
    fd: BorrowedFd<'_>,
    offset: i64,
    length: i64,
    flags: SyncFileRangeFlags,
) -> Result<(), SyscallError> {
    decode_zero(unsafe {
        abi::invoke(
            SYNC_FILE_RANGE,
            [
                fd.as_raw_fd() as usize,
                offset as usize,
                length as usize,
                flags.0 as usize,
                0,
                0,
            ],
        )
    })
}

#[repr(u32)]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum RenameMode {
    Replace = 0,
    NoReplace = 1,
    Exchange = 2,
}

/// Performs a directory-relative rename. Exchange requires both names to
/// exist. NoReplace requires filesystem support and an unused destination name.
pub fn renameat2(
    old_dir: Directory<'_>,
    old_path: &CStr,
    new_dir: Directory<'_>,
    new_path: &CStr,
    mode: RenameMode,
) -> Result<(), SyscallError> {
    decode_zero(unsafe {
        abi::invoke(
            RENAMEAT2,
            [
                old_dir.argument(),
                old_path.as_ptr() as usize,
                new_dir.argument(),
                new_path.as_ptr() as usize,
                mode as usize,
                0,
            ],
        )
    })
}

/// Copies a filesystem-supported regular-file range using native flags 0.
/// Either offset can be explicit or taken from its open file description.
/// Explicit positions advance by the returned progress on success. The copied
/// count can be shorter than requested, and a zero count reports no progress.
pub fn copy_file_range(
    input: BorrowedFd<'_>,
    input_offset: Option<&mut i64>,
    output: BorrowedFd<'_>,
    output_offset: Option<&mut i64>,
    length: usize,
) -> Result<usize, SyscallError> {
    let original_input = input_offset.as_deref().copied();
    let original_output = output_offset.as_deref().copied();
    let mut observed_input = original_input;
    let mut observed_output = original_output;
    let raw = unsafe {
        abi::invoke(
            COPY_FILE_RANGE,
            [
                input.as_raw_fd() as usize,
                offset_address(&mut observed_input),
                output.as_raw_fd() as usize,
                offset_address(&mut observed_output),
                length,
                0,
            ],
        )
    };
    let progress = decode_write(raw, length)?;
    let progress_i64 = progress as i64; // A successful native result is at most isize::MAX.
    if !valid_advance(original_input, observed_input, progress_i64)
        || !valid_advance(original_output, observed_output, progress_i64)
    {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    if let (Some(destination), Some(offset)) = (input_offset, observed_input) {
        *destination = offset;
    }
    if let (Some(destination), Some(offset)) = (output_offset, observed_output) {
        *destination = offset;
    }
    Ok(progress)
}

fn offset_address(offset: &mut Option<i64>) -> usize {
    offset
        .as_mut()
        .map_or(0, |offset| offset as *mut i64 as usize)
}

fn valid_advance(original: Option<i64>, observed: Option<i64>, progress: i64) -> bool {
    match original {
        Some(value) => value
            .checked_add(progress)
            .is_some_and(|next| observed == Some(next)),
        None => observed.is_none(),
    }
}
