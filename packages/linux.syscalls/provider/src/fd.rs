use super::{abi, decode_nonnegative, decode_write, decode_zero, SyscallError};
use std::ffi::CStr;
use std::os::fd::{AsFd, AsRawFd, BorrowedFd, RawFd};

pub const O_RDONLY: i32 = 0;
pub const O_WRONLY: i32 = 1;
pub const O_RDWR: i32 = 2;
pub const O_CREAT: i32 = 0o100;
pub const O_EXCL: i32 = 0o200;
pub const O_TRUNC: i32 = 0o1000;
pub const O_APPEND: i32 = 0o2000;
pub const O_NONBLOCK: i32 = 0o4000;
pub const O_DIRECTORY: i32 = 0o200000;
pub const O_NOFOLLOW: i32 = 0o400000;
pub const O_CLOEXEC: i32 = 0o2000000;
pub const AT_REMOVEDIR: i32 = 0x200;
pub const AT_SYMLINK_FOLLOW: i32 = 0x400;
pub const AT_SYMLINK_NOFOLLOW: i32 = 0x100;
pub const AT_EMPTY_PATH: i32 = 0x1000;
pub const AT_EACCESS: i32 = 0x200;
pub const LOCK_SH: i32 = 1;
pub const LOCK_EX: i32 = 2;
pub const LOCK_NB: i32 = 4;
pub const LOCK_UN: i32 = 8;

/// Owns one Linux descriptor. Dropping closes it once. Use `close` to inspect
/// the result. Distinct open descriptors can refer to the same kernel object.
#[derive(Debug)]
pub struct LinuxFd(RawFd);

impl LinuxFd {
    pub fn borrow(&self) -> BorrowedFd<'_> {
        // The descriptor stays owned and open for the borrow's lifetime.
        unsafe { BorrowedFd::borrow_raw(self.0) }
    }

    pub(super) fn from_result(raw: isize) -> Result<Self, SyscallError> {
        let descriptor = decode_nonnegative(raw)?;
        let descriptor =
            RawFd::try_from(descriptor).map_err(|_| SyscallError::UnexpectedReturn(raw))?;
        Ok(Self(descriptor))
    }
}

impl AsFd for LinuxFd {
    fn as_fd(&self) -> BorrowedFd<'_> {
        self.borrow()
    }
}

impl AsRawFd for LinuxFd {
    fn as_raw_fd(&self) -> RawFd {
        self.0
    }
}

impl Drop for LinuxFd {
    fn drop(&mut self) {
        let _ = close_raw(self.0);
    }
}

fn close_raw(fd: RawFd) -> Result<(), SyscallError> {
    decode_zero(unsafe { abi::call(abi::CLOSE, [fd as usize, 0, 0, 0, 0, 0]) })
}

/// Consumes ownership even if Linux reports an error. Retrying close can
/// affect an unrelated descriptor if another thread reuses its number.
pub fn close(fd: LinuxFd) -> Result<(), SyscallError> {
    let raw = fd.0;
    std::mem::forget(fd);
    close_raw(raw)
}

#[derive(Clone, Copy, Debug)]
pub enum Directory<'a> {
    Current,
    Borrowed(BorrowedFd<'a>),
}

impl Directory<'_> {
    pub(super) fn argument(self) -> usize {
        match self {
            Self::Current => -100_i32 as usize, // AT_FDCWD
            Self::Borrowed(fd) => fd.as_raw_fd() as usize,
        }
    }
}

#[derive(Clone, Copy, Debug)]
pub struct OpenOptions {
    pub flags: i32,
    pub mode: u32,
}

/// Returns an owned descriptor with FD_CLOEXEC set atomically.
pub fn openat(
    dir: Directory<'_>,
    path: &CStr,
    options: OpenOptions,
) -> Result<LinuxFd, SyscallError> {
    let raw = unsafe {
        abi::call(
            abi::OPENAT,
            [
                dir.argument(),
                path.as_ptr() as usize,
                (options.flags | O_CLOEXEC) as usize,
                options.mode as usize,
                0,
                0,
            ],
        )
    };
    LinuxFd::from_result(raw)
}

/// Returns the read endpoint followed by the write endpoint. Both are owned
/// and have FD_CLOEXEC set atomically.
pub fn pipe2(flags: i32) -> Result<(LinuxFd, LinuxFd), SyscallError> {
    let mut descriptors = [-1_i32; 2];
    let raw = unsafe {
        abi::call(
            abi::PIPE2,
            [
                descriptors.as_mut_ptr() as usize,
                (flags | O_CLOEXEC) as usize,
                0,
                0,
                0,
                0,
            ],
        )
    };
    decode_pipe(raw, descriptors)
}

pub(super) fn decode_pipe(
    raw: isize,
    descriptors: [i32; 2],
) -> Result<(LinuxFd, LinuxFd), SyscallError> {
    decode_zero(raw)?;
    match (descriptors[0], descriptors[1]) {
        (read, write) if read >= 0 && write >= 0 && read != write => {
            Ok((LinuxFd(read), LinuxFd(write)))
        }
        (read, write) => {
            if read >= 0 {
                let _ = close_raw(read);
            }
            if write >= 0 && write != read {
                let _ = close_raw(write);
            }
            Err(SyscallError::UnexpectedReturn(raw))
        }
    }
}

pub fn flock(fd: BorrowedFd<'_>, operation: i32) -> Result<(), SyscallError> {
    decode_zero(unsafe {
        abi::call(
            abi::FLOCK,
            [fd.as_raw_fd() as usize, operation as usize, 0, 0, 0, 0],
        )
    })
}

pub fn fsync(fd: BorrowedFd<'_>) -> Result<(), SyscallError> {
    decode_zero(unsafe { abi::call(abi::FSYNC, [fd.as_raw_fd() as usize, 0, 0, 0, 0, 0]) })
}

pub fn fdatasync(fd: BorrowedFd<'_>) -> Result<(), SyscallError> {
    decode_zero(unsafe { abi::call(abi::FDATASYNC, [fd.as_raw_fd() as usize, 0, 0, 0, 0, 0]) })
}

pub fn ftruncate(fd: BorrowedFd<'_>, length: i64) -> Result<(), SyscallError> {
    decode_zero(unsafe {
        abi::call(
            abi::FTRUNCATE,
            [fd.as_raw_fd() as usize, length as usize, 0, 0, 0, 0],
        )
    })
}

pub fn syncfs(fd: BorrowedFd<'_>) -> Result<(), SyscallError> {
    decode_zero(unsafe { abi::call(abi::SYNCFS, [fd.as_raw_fd() as usize, 0, 0, 0, 0, 0]) })
}

#[repr(usize)]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SeekOrigin {
    Start = 0,
    Current = 1,
    End = 2,
    Data = 3,
    Hole = 4,
}

/// Positions a seekable descriptor with nonnegative signed 64-bit offsets.
pub fn lseek(fd: BorrowedFd<'_>, offset: i64, origin: SeekOrigin) -> Result<u64, SyscallError> {
    let raw = unsafe {
        abi::call(
            abi::LSEEK,
            [
                fd.as_raw_fd() as usize,
                offset as usize,
                origin as usize,
                0,
                0,
                0,
            ],
        )
    };
    decode_nonnegative(raw).map(|value| value as u64)
}

/// Duplicates the open file description. Native dup leaves CLOEXEC clear.
pub fn dup(fd: BorrowedFd<'_>) -> Result<LinuxFd, SyscallError> {
    let raw = unsafe { abi::call(abi::DUP, [fd.as_raw_fd() as usize, 0, 0, 0, 0, 0]) };
    LinuxFd::from_result(raw)
}

/// Uses the typed F_DUPFD_CLOEXEC command. The new descriptor is at least
/// `minimum` and shares the original open file description.
pub fn dup_cloexec(fd: BorrowedFd<'_>, minimum: i32) -> Result<LinuxFd, SyscallError> {
    const F_DUPFD_CLOEXEC: usize = 1030;
    let raw = unsafe {
        abi::call(
            abi::FCNTL,
            [
                fd.as_raw_fd() as usize,
                F_DUPFD_CLOEXEC,
                minimum as usize,
                0,
                0,
                0,
            ],
        )
    };
    LinuxFd::from_result(raw)
}

pub fn fchmod(fd: BorrowedFd<'_>, mode: u16) -> Result<(), SyscallError> {
    decode_zero(unsafe {
        abi::call(
            abi::FCHMOD,
            [fd.as_raw_fd() as usize, mode as usize, 0, 0, 0, 0],
        )
    })
}

pub fn fchmodat2(
    dir: Directory<'_>,
    path: &CStr,
    mode: u16,
    flags: i32,
) -> Result<(), SyscallError> {
    decode_zero(unsafe {
        abi::call(
            abi::FCHMODAT2,
            [
                dir.argument(),
                path.as_ptr() as usize,
                mode as usize,
                flags as usize,
                0,
                0,
            ],
        )
    })
}

/// Observes the access check based on the credentials and flags of this call.
/// A later filesystem operation carries out its own permission check.
pub fn faccessat2(
    dir: Directory<'_>,
    path: &CStr,
    mode: i32,
    flags: i32,
) -> Result<(), SyscallError> {
    decode_zero(unsafe {
        abi::call(
            abi::FACCESSAT2,
            [
                dir.argument(),
                path.as_ptr() as usize,
                mode as usize,
                flags as usize,
                0,
                0,
            ],
        )
    })
}

pub fn mkdirat(dir: Directory<'_>, path: &CStr, mode: u32) -> Result<(), SyscallError> {
    decode_zero(unsafe {
        abi::call(
            abi::MKDIRAT,
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

pub fn unlinkat(dir: Directory<'_>, path: &CStr, flags: i32) -> Result<(), SyscallError> {
    decode_zero(unsafe {
        abi::call(
            abi::UNLINKAT,
            [
                dir.argument(),
                path.as_ptr() as usize,
                flags as usize,
                0,
                0,
                0,
            ],
        )
    })
}

pub fn renameat(
    old_dir: Directory<'_>,
    old_path: &CStr,
    new_dir: Directory<'_>,
    new_path: &CStr,
) -> Result<(), SyscallError> {
    decode_zero(unsafe {
        abi::call(
            abi::RENAMEAT,
            [
                old_dir.argument(),
                old_path.as_ptr() as usize,
                new_dir.argument(),
                new_path.as_ptr() as usize,
                0,
                0,
            ],
        )
    })
}

pub fn linkat(
    old_dir: Directory<'_>,
    old_path: &CStr,
    new_dir: Directory<'_>,
    new_path: &CStr,
    flags: i32,
) -> Result<(), SyscallError> {
    decode_zero(unsafe {
        abi::call(
            abi::LINKAT,
            [
                old_dir.argument(),
                old_path.as_ptr() as usize,
                new_dir.argument(),
                new_path.as_ptr() as usize,
                flags as usize,
                0,
            ],
        )
    })
}

pub fn symlinkat(target: &CStr, dir: Directory<'_>, path: &CStr) -> Result<(), SyscallError> {
    decode_zero(unsafe {
        abi::call(
            abi::SYMLINKAT,
            [
                target.as_ptr() as usize,
                dir.argument(),
                path.as_ptr() as usize,
                0,
                0,
                0,
            ],
        )
    })
}

/// Returns the link bytes written. Linux need not NUL-terminate them.
pub fn readlinkat(
    dir: Directory<'_>,
    path: &CStr,
    buffer: &mut [u8],
) -> Result<usize, SyscallError> {
    let count = i32::try_from(buffer.len())
        .map_err(|_| SyscallError::InvalidInput("readlinkat capacity exceeds Linux int"))?;
    let raw = unsafe {
        abi::call(
            abi::READLINKAT,
            [
                dir.argument(),
                path.as_ptr() as usize,
                buffer.as_mut_ptr() as usize,
                count as usize,
                0,
                0,
            ],
        )
    };
    decode_write(raw, buffer.len())
}
