use super::{abi, decode_nonnegative, SyscallError};
use std::io::{IoSlice, IoSliceMut};
use std::os::fd::{AsRawFd, BorrowedFd};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ReadOutcome {
    Progress(usize),
    /// Zero bytes returned by the kernel for a nonempty request. The descriptor
    /// determines whether zero implies EOF, for example on a drained pipe.
    Eof,
}

/// Requests of length zero that succeed report zero progress. For a nonempty
/// request, `Eof` represents a zero kernel result under the descriptor's semantics.
pub fn decode_read(raw: isize, requested: usize) -> Result<ReadOutcome, SyscallError> {
    match decode_write(raw, requested)? {
        0 if requested != 0 => Ok(ReadOutcome::Eof),
        count => Ok(ReadOutcome::Progress(count)),
    }
}

pub fn decode_write(raw: isize, requested: usize) -> Result<usize, SyscallError> {
    let count = decode_nonnegative(raw)?;
    if count > requested {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    Ok(count)
}

pub fn read(fd: BorrowedFd<'_>, buffer: &mut [u8]) -> Result<ReadOutcome, SyscallError> {
    // The kernel may write only within the exclusive slice for this call.
    let raw = unsafe {
        abi::invoke(
            abi::READ,
            [
                fd.as_raw_fd() as usize,
                buffer.as_mut_ptr() as usize,
                buffer.len(),
                0,
                0,
                0,
            ],
        )
    };
    decode_read(raw, buffer.len())
}

pub fn write(fd: BorrowedFd<'_>, buffer: &[u8]) -> Result<usize, SyscallError> {
    // The kernel may read from the immutable slice for this call.
    let raw = unsafe {
        abi::invoke(
            abi::WRITE,
            [
                fd.as_raw_fd() as usize,
                buffer.as_ptr() as usize,
                buffer.len(),
                0,
                0,
                0,
            ],
        )
    };
    decode_write(raw, buffer.len())
}

pub fn pread64(
    fd: BorrowedFd<'_>,
    buffer: &mut [u8],
    offset: i64,
) -> Result<ReadOutcome, SyscallError> {
    let raw = unsafe {
        abi::invoke(
            abi::PREAD64,
            [
                fd.as_raw_fd() as usize,
                buffer.as_mut_ptr() as usize,
                buffer.len(),
                offset as usize,
                0,
                0,
            ],
        )
    };
    decode_read(raw, buffer.len())
}

pub fn pwrite64(fd: BorrowedFd<'_>, buffer: &[u8], offset: i64) -> Result<usize, SyscallError> {
    let raw = unsafe {
        abi::invoke(
            abi::PWRITE64,
            [
                fd.as_raw_fd() as usize,
                buffer.as_ptr() as usize,
                buffer.len(),
                offset as usize,
                0,
                0,
            ],
        )
    };
    decode_write(raw, buffer.len())
}

#[repr(C)]
pub(super) struct Iovec {
    address: usize,
    len: usize,
}

pub(super) fn iovec_len(vectors: &[Iovec]) -> Result<usize, SyscallError> {
    vectors.iter().try_fold(0_usize, |total, vector| {
        total
            .checked_add(vector.len)
            .ok_or(SyscallError::InvalidInput("I/O vector byte count overflow"))
    })
}

pub(super) fn read_iovecs(buffers: &mut [IoSliceMut<'_>]) -> Vec<Iovec> {
    buffers
        .iter_mut()
        .map(|buffer| Iovec {
            address: buffer.as_mut_ptr() as usize,
            len: buffer.len(),
        })
        .collect()
}

pub(super) fn write_iovecs(buffers: &[IoSlice<'_>]) -> Vec<Iovec> {
    buffers
        .iter()
        .map(|buffer| Iovec {
            address: buffer.as_ptr() as usize,
            len: buffer.len(),
        })
        .collect()
}

pub fn readv(
    fd: BorrowedFd<'_>,
    buffers: &mut [IoSliceMut<'_>],
) -> Result<ReadOutcome, SyscallError> {
    let vectors = read_iovecs(buffers);
    let requested = iovec_len(&vectors)?;
    // Source slices remain exclusively borrowed during readv. The adapter
    // constructs its own C-layout iovecs rather than borrowing Rust layout.
    let raw = unsafe {
        abi::invoke(
            abi::READV,
            [
                fd.as_raw_fd() as usize,
                vectors.as_ptr() as usize,
                vectors.len(),
                0,
                0,
                0,
            ],
        )
    };
    decode_read(raw, requested)
}

pub fn writev(fd: BorrowedFd<'_>, buffers: &[IoSlice<'_>]) -> Result<usize, SyscallError> {
    let vectors = write_iovecs(buffers);
    let requested = iovec_len(&vectors)?;
    let raw = unsafe {
        abi::invoke(
            abi::WRITEV,
            [
                fd.as_raw_fd() as usize,
                vectors.as_ptr() as usize,
                vectors.len(),
                0,
                0,
                0,
            ],
        )
    };
    decode_write(raw, requested)
}
