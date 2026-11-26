use super::io::{iovec_len, read_iovecs, write_iovecs, Iovec};
use super::{abi, decode_read, decode_write, ReadOutcome, SyscallError};
use std::io::{IoSlice, IoSliceMut};
use std::os::fd::{AsRawFd, BorrowedFd};

const PREADV: usize = 295;
const PWRITEV: usize = 296;
const PREADV2: usize = 327;
const PWRITEV2: usize = 328;

/// Reads from an explicit offset without moving the open file description cursor.
pub fn preadv(
    fd: BorrowedFd<'_>,
    buffers: &mut [IoSliceMut<'_>],
    offset: i64,
) -> Result<ReadOutcome, SyscallError> {
    read_at(PREADV, fd, buffers, offset)
}

/// Writes at an explicit offset without moving the open file description cursor.
/// Linux can append instead when the open file description has O_APPEND set.
pub fn pwritev(
    fd: BorrowedFd<'_>,
    buffers: &[IoSlice<'_>],
    offset: i64,
) -> Result<usize, SyscallError> {
    write_at(PWRITEV, fd, buffers, offset, WriteVectorMode::Default)
}

/// Reads with Linux flags 0. `None` uses and advances the current file cursor.
pub fn preadv2(
    fd: BorrowedFd<'_>,
    buffers: &mut [IoSliceMut<'_>],
    offset: Option<i64>,
) -> Result<ReadOutcome, SyscallError> {
    read_at(PREADV2, fd, buffers, native_offset(offset)?)
}

#[repr(u32)]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum WriteVectorMode {
    /// Use native flags 0, preserving any O_APPEND behavior of the opened file.
    Default = 0,
    /// Request RWF_APPEND for this operation, including on an ordinary writable file.
    Append = 0x10,
}

/// Writes with typed flags. `None` uses current-cursor semantics, including
/// advancing to the resulting position when append is selected.
pub fn pwritev2(
    fd: BorrowedFd<'_>,
    buffers: &[IoSlice<'_>],
    offset: Option<i64>,
    mode: WriteVectorMode,
) -> Result<usize, SyscallError> {
    write_at(PWRITEV2, fd, buffers, native_offset(offset)?, mode)
}

fn native_offset(offset: Option<i64>) -> Result<i64, SyscallError> {
    match offset {
        Some(offset) if offset >= 0 => Ok(offset),
        Some(_) => Err(SyscallError::InvalidInput(
            "explicit vector I/O offset must be nonnegative",
        )),
        None => Ok(-1),
    }
}

fn read_at(
    number: usize,
    fd: BorrowedFd<'_>,
    buffers: &mut [IoSliceMut<'_>],
    offset: i64,
) -> Result<ReadOutcome, SyscallError> {
    let vectors = read_iovecs(buffers);
    let requested = iovec_len(&vectors)?;
    // The outer mutable borrow keeps all destination slices live and disjoint.
    let raw = unsafe { invoke(number, fd, &vectors, offset, 0) };
    decode_read(raw, requested)
}

fn write_at(
    number: usize,
    fd: BorrowedFd<'_>,
    buffers: &[IoSlice<'_>],
    offset: i64,
    mode: WriteVectorMode,
) -> Result<usize, SyscallError> {
    let vectors = write_iovecs(buffers);
    let requested = iovec_len(&vectors)?;
    // Each source slice remains live and shared during the kernel read.
    let raw = unsafe { invoke(number, fd, &vectors, offset, mode as usize) };
    decode_write(raw, requested)
}

/// The caller provides live and appropriately borrowed buffers for the chosen
/// read or write operation. Native x86-64 LP64 places the whole signed offset
/// in pos_l (r10); pos_h (r8) is zero. The v2 flags are the sixth argument (r9).
/// Linux v6.12 documents the conversion in fs/read_write.c `pos_from_hilo`.
unsafe fn invoke(
    number: usize,
    fd: BorrowedFd<'_>,
    vectors: &[Iovec],
    offset: i64,
    flags: usize,
) -> isize {
    unsafe {
        abi::call(
            number,
            [
                fd.as_raw_fd() as usize,
                vectors.as_ptr() as usize,
                vectors.len(),
                offset as usize,
                0,
                flags,
            ],
        )
    }
}
