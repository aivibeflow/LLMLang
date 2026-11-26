//! Native descriptor-table flag updates and file page-cache observations.
use std::mem::{align_of, offset_of, size_of};
use std::os::fd::{AsRawFd, BorrowedFd};

use crate::{abi, decode_zero, SyscallError};

const CLOSE_RANGE: usize = 436;
const CACHESTAT: usize = 451;
const CLOSE_RANGE_CLOEXEC: usize = 1 << 2;

/// Mark open descriptors in the inclusive range close-on-exec. This changes
/// descriptor flags in the calling thread's current descriptor table. Threads
/// sharing that table observe the change.
pub fn close_range_cloexec(first: u32, last: u32) -> Result<(), SyscallError> {
    if first > last {
        return Err(SyscallError::InvalidInput("reversed descriptor range"));
    }
    decode_zero(unsafe {
        abi::call(
            CLOSE_RANGE,
            [first as usize, last as usize, CLOSE_RANGE_CLOEXEC, 0, 0, 0],
        )
    })
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(C)]
pub struct CacheStatRange {
    pub offset: u64,
    /// A zero length requests the range from offset through the end of the file.
    pub length: u64,
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
#[repr(C)]
pub struct CacheStat {
    pub cached: u64,
    pub dirty: u64,
    pub writeback: u64,
    pub evicted: u64,
    pub recently_evicted: u64,
}

const _: () = {
    assert!(size_of::<CacheStatRange>() == 16);
    assert!(align_of::<CacheStatRange>() == 8);
    assert!(offset_of!(CacheStatRange, length) == 8);
    assert!(size_of::<CacheStat>() == 40);
    assert!(align_of::<CacheStat>() == 8);
    assert!(offset_of!(CacheStat, recently_evicted) == 32);
};

/// Observe page-cache counts without moving the file offset. Linux can change
/// the counts independently as pages are written back or evicted.
pub fn cachestat(file: BorrowedFd<'_>, range: CacheStatRange) -> Result<CacheStat, SyscallError> {
    if range.length != 0 && range.offset.checked_add(range.length - 1).is_none() {
        return Err(SyscallError::InvalidInput("cache range exceeds u64"));
    }

    let mut stats = CacheStat::default();
    decode_zero(unsafe {
        abi::call(
            CACHESTAT,
            [
                file.as_raw_fd() as usize,
                std::ptr::from_ref(&range) as usize,
                std::ptr::from_mut(&mut stats) as usize,
                0,
                0,
                0,
            ],
        )
    })?;
    Ok(stats)
}
