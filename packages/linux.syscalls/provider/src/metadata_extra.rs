use super::{abi, decode_zero, Directory, SyscallError};
use std::ffi::CStr;
use std::os::fd::{AsRawFd, BorrowedFd};

const CHOWN: usize = 92;
const FCHOWN: usize = 93;
const LCHOWN: usize = 94;
const UTIME: usize = 132;
const UTIMES: usize = 235;
const FCHOWNAT: usize = 260;
const FUTIMESAT: usize = 261;
const UTIMENSAT: usize = 280;

/// Changes the requested IDs on the file reached by following the path. Linux
/// applies its usual ownership, mode, and ctime rules. `None` leaves that ID unchanged.
pub fn chown(path: &CStr, owner: Option<u32>, group: Option<u32>) -> Result<(), SyscallError> {
    change_ids(CHOWN, path.as_ptr() as usize, owner, group)
}

/// Changes the requested IDs without following a final symbolic link.
pub fn lchown(path: &CStr, owner: Option<u32>, group: Option<u32>) -> Result<(), SyscallError> {
    change_ids(LCHOWN, path.as_ptr() as usize, owner, group)
}

pub fn fchown(
    fd: BorrowedFd<'_>,
    owner: Option<u32>,
    group: Option<u32>,
) -> Result<(), SyscallError> {
    change_ids(FCHOWN, fd.as_raw_fd() as usize, owner, group)
}

/// Changes ownership on a directory-relative path. Linux interprets the
/// supplied AT flags, including `AT_SYMLINK_NOFOLLOW` and `AT_EMPTY_PATH`.
pub fn fchownat(
    dir: Directory<'_>,
    path: &CStr,
    owner: Option<u32>,
    group: Option<u32>,
    flags: i32,
) -> Result<(), SyscallError> {
    let owner = id_argument(owner)?;
    let group = id_argument(group)?;
    decode_zero(unsafe {
        abi::invoke(
            FCHOWNAT,
            [
                dir.argument(),
                path.as_ptr() as usize,
                owner,
                group,
                flags as usize,
                0,
            ],
        )
    })
}

fn change_ids(
    number: usize,
    subject: usize,
    owner: Option<u32>,
    group: Option<u32>,
) -> Result<(), SyscallError> {
    let owner = id_argument(owner)?;
    let group = id_argument(group)?;
    decode_zero(unsafe { abi::invoke(number, [subject, owner, group, 0, 0, 0]) })
}

fn id_argument(id: Option<u32>) -> Result<usize, SyscallError> {
    match id {
        None => Ok(u32::MAX as usize),
        Some(u32::MAX) => Err(SyscallError::InvalidInput(
            "explicit Linux ID cannot be the unchanged sentinel",
        )),
        Some(id) => Ok(id as usize),
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct FileTimes<T> {
    pub accessed: T,
    pub modified: T,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct MicroTimestamp {
    seconds: i64,
    micros: u32,
}

impl MicroTimestamp {
    pub fn new(seconds: i64, micros: u32) -> Result<Self, SyscallError> {
        if micros >= 1_000_000 {
            return Err(SyscallError::InvalidInput(
                "microseconds must be in 0..1_000_000",
            ));
        }
        Ok(Self { seconds, micros })
    }

    fn native(self) -> NativeTimestamp {
        NativeTimestamp {
            seconds: self.seconds,
            fraction: self.micros as i64,
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct NanoTimestamp {
    seconds: i64,
    nanos: u32,
}

impl NanoTimestamp {
    pub const NOW: Self = Self {
        seconds: 0,
        nanos: (1 << 30) - 1,
    };
    pub const OMIT: Self = Self {
        seconds: 0,
        nanos: (1 << 30) - 2,
    };

    pub fn exact(seconds: i64, nanos: u32) -> Result<Self, SyscallError> {
        if nanos >= 1_000_000_000 {
            return Err(SyscallError::InvalidInput(
                "nanoseconds must be in 0..1_000_000_000",
            ));
        }
        Ok(Self { seconds, nanos })
    }

    fn native(self) -> NativeTimestamp {
        NativeTimestamp {
            seconds: self.seconds,
            fraction: self.nanos as i64,
        }
    }
}

// Native Linux x86-64 old timeval and kernel timespec have the same layout.
// The fraction is interpreted by the individual syscall as microseconds or nanoseconds.
#[repr(C)]
struct NativeTimestamp {
    seconds: i64,
    fraction: i64,
}

/// Updates both file timestamps to whole seconds; `None` asks the kernel for now.
pub fn utime(path: &CStr, times: Option<FileTimes<i64>>) -> Result<(), SyscallError> {
    // Native struct utimbuf has two consecutive kernel time_t fields.
    let values = times.map(|times| [times.accessed, times.modified]);
    decode_zero(unsafe {
        abi::invoke(
            UTIME,
            [path.as_ptr() as usize, address(&values), 0, 0, 0, 0],
        )
    })
}

/// Updates the timestamps with microsecond precision; `None` uses kernel time.
pub fn utimes(path: &CStr, times: Option<FileTimes<MicroTimestamp>>) -> Result<(), SyscallError> {
    let values = times.map(|times| [times.accessed.native(), times.modified.native()]);
    decode_zero(unsafe {
        abi::invoke(
            UTIMES,
            [path.as_ptr() as usize, address(&values), 0, 0, 0, 0],
        )
    })
}

/// Updates the timestamps of a non-null directory-relative pathname.
pub fn futimesat(
    dir: Directory<'_>,
    path: &CStr,
    times: Option<FileTimes<MicroTimestamp>>,
) -> Result<(), SyscallError> {
    let values = times.map(|times| [times.accessed.native(), times.modified.native()]);
    decode_zero(unsafe {
        abi::invoke(
            FUTIMESAT,
            [
                dir.argument(),
                path.as_ptr() as usize,
                address(&values),
                0,
                0,
                0,
            ],
        )
    })
}

/// Updates timestamps with nanosecond precision and supports per-field `NOW`
/// and `OMIT` selectors. Linux interprets the supplied AT flags and can ignore
/// the pathname when both fields request `OMIT`.
pub fn utimensat(
    dir: Directory<'_>,
    path: &CStr,
    times: Option<FileTimes<NanoTimestamp>>,
    flags: i32,
) -> Result<(), SyscallError> {
    let values = times.map(|times| [times.accessed.native(), times.modified.native()]);
    decode_zero(unsafe {
        abi::invoke(
            UTIMENSAT,
            [
                dir.argument(),
                path.as_ptr() as usize,
                address(&values),
                flags as usize,
                0,
                0,
            ],
        )
    })
}

fn address<T>(value: &Option<T>) -> usize {
    value.as_ref().map_or(0, |value| value as *const T as usize)
}

#[cfg(test)]
mod layout_tests {
    use super::*;
    use std::mem::{align_of, offset_of, size_of};

    #[test]
    fn native_timestamp_pairs_match_x86_64_abi() {
        assert_eq!(size_of::<[i64; 2]>(), 16);
        assert_eq!(size_of::<NativeTimestamp>(), 16);
        assert_eq!(align_of::<NativeTimestamp>(), 8);
        assert_eq!(offset_of!(NativeTimestamp, fraction), 8);
        assert_eq!(size_of::<[NativeTimestamp; 2]>(), 32);
        assert_eq!(NanoTimestamp::NOW.native().fraction, 1_073_741_823);
        assert_eq!(NanoTimestamp::OMIT.native().fraction, 1_073_741_822);
    }
}
