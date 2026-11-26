use super::io::{iovec_len, read_iovecs};
use super::{
    abi, decode_read, decode_write, pipe2, LinuxFd, ReadOutcome, SyscallError, O_NONBLOCK,
};
use std::io::IoSliceMut;
use std::os::fd::{AsFd, AsRawFd, BorrowedFd};

const SPLICE: usize = 275;
const TEE: usize = 276;
const VMSPLICE: usize = 278;

/// Selects whether to request nonblocking handling of pipe queues.
#[repr(u32)]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SpliceMode {
    Blocking = 0,
    NonBlocking = 2, // Linux SPLICE_F_NONBLOCK
}

/// Transfers a prefix between descriptors, at least one of which must be a
/// pipe. Explicit offsets are valid only for the nonpipe descriptor and
/// advance by actual progress. Otherwise Linux uses the descriptor cursor.
pub fn splice(
    input: BorrowedFd<'_>,
    input_offset: Option<&mut i64>,
    output: BorrowedFd<'_>,
    output_offset: Option<&mut i64>,
    count: usize,
    mode: SpliceMode,
) -> Result<usize, SyscallError> {
    let original_input = input_offset.as_deref().copied();
    let original_output = output_offset.as_deref().copied();
    let mut observed_input = original_input;
    let mut observed_output = original_output;
    let raw = unsafe {
        abi::call(
            SPLICE,
            [
                input.as_raw_fd() as usize,
                offset_address(&mut observed_input),
                output.as_raw_fd() as usize,
                offset_address(&mut observed_output),
                count,
                mode as usize,
            ],
        )
    };
    let progress = decode_write(raw, count)?;
    if !valid_advance(original_input, observed_input, progress as i64)
        || !valid_advance(original_output, observed_output, progress as i64)
    {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    if let (Some(target), Some(offset)) = (input_offset, observed_input) {
        *target = offset;
    }
    if let (Some(target), Some(offset)) = (output_offset, observed_output) {
        *target = offset;
    }
    Ok(progress)
}

fn offset_address(offset: &mut Option<i64>) -> usize {
    offset
        .as_mut()
        .map_or(0, |value| value as *mut i64 as usize)
}

fn valid_advance(original: Option<i64>, observed: Option<i64>, progress: i64) -> bool {
    match original {
        Some(value) => value
            .checked_add(progress)
            .is_some_and(|next| observed == Some(next)),
        None => observed.is_none(),
    }
}

/// Duplicates a prefix from one pipe into a distinct pipe. The input queue
/// keeps its original data and Linux can return a partial or zero count.
pub fn tee(
    input: BorrowedFd<'_>,
    output: BorrowedFd<'_>,
    count: usize,
    mode: SpliceMode,
) -> Result<usize, SyscallError> {
    let raw = unsafe {
        abi::call(
            TEE,
            [
                input.as_raw_fd() as usize,
                output.as_raw_fd() as usize,
                count,
                mode as usize,
                0,
                0,
            ],
        )
    };
    decode_write(raw, count)
}

/// Owns the immutable read-only endpoint returned by `vmsplice_pipe`.
#[derive(Debug)]
pub struct VmspliceReadEnd(LinuxFd);

impl VmspliceReadEnd {
    pub fn borrow(&self) -> BorrowedFd<'_> {
        self.0.borrow()
    }

    pub fn into_fd(self) -> LinuxFd {
        self.0
    }
}

impl AsFd for VmspliceReadEnd {
    fn as_fd(&self) -> BorrowedFd<'_> {
        self.borrow()
    }
}

/// Creates a pipe through `pipe2` with atomic CLOEXEC on both endpoints and
/// tracks the first as read-only. NonBlocking also sets O_NONBLOCK on both.
pub fn vmsplice_pipe(mode: SpliceMode) -> Result<(VmspliceReadEnd, LinuxFd), SyscallError> {
    let flags = match mode {
        SpliceMode::Blocking => 0,
        SpliceMode::NonBlocking => O_NONBLOCK,
    };
    let (reader, writer) = pipe2(flags)?;
    Ok((VmspliceReadEnd(reader), writer))
}

/// Copies from a pipe into disjoint user buffers through native `vmsplice`.
/// The owned endpoint comes from `pipe2`'s read-only slot and cannot enter
/// the Linux user-to-pipe branch. In Linux v6.12 `fs/pipe.c` sets the read
/// endpoint to O_RDONLY. `fs/splice.c` then selects ITER_DEST and uses
/// `copy_page_to_iter` before returning, without retaining user pages.
pub fn vmsplice(
    input: &VmspliceReadEnd,
    buffers: &mut [IoSliceMut<'_>],
    mode: SpliceMode,
) -> Result<ReadOutcome, SyscallError> {
    let vectors = read_iovecs(buffers);
    let requested = iovec_len(&vectors)?;
    let raw = unsafe {
        abi::call(
            VMSPLICE,
            [
                input.borrow().as_raw_fd() as usize,
                vectors.as_ptr() as usize,
                vectors.len(),
                mode as usize,
                0,
                0,
            ],
        )
    };
    decode_read(raw, requested)
}
