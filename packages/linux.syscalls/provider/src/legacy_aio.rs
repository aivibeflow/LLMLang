//! Owned Linux AIO contexts for fsync and cancellable private-pipe polling.

use super::{abi, decode_nonnegative, decode_zero, pipe2, LinuxFd, SyscallError};
use std::fmt;
use std::mem::{align_of, offset_of, size_of};
use std::num::NonZeroUsize;
use std::os::fd::{AsRawFd, BorrowedFd};
use std::sync::atomic::{AtomicU64, Ordering};

const IO_SETUP: usize = 206;
const IO_DESTROY: usize = 207;
const IO_GETEVENTS: usize = 208;
const IO_SUBMIT: usize = 209;
const IO_CANCEL: usize = 210;
const IO_PGETEVENTS: usize = 333;
const IOCB_CMD_FSYNC: u16 = 2;
const IOCB_CMD_POLL: u16 = 5;
const POLLIN: u64 = 1;
const MAX_AIO_ENTRIES: u32 = 16;
const EINPROGRESS: isize = 115;
static NEXT_CONTEXT: AtomicU64 = AtomicU64::new(1);

#[repr(C)]
#[derive(Default)]
struct NativeIocb {
    data: u64,
    key: u32,
    rw_flags: u32,
    opcode: u16,
    request_priority: i16,
    descriptor: u32,
    buffer: u64,
    bytes: u64,
    offset: i64,
    reserved: u64,
    flags: u32,
    event_descriptor: u32,
}

#[repr(C)]
#[derive(Clone, Copy, Default)]
struct NativeIoEvent {
    data: u64,
    object: u64,
    result: i64,
    secondary_result: i64,
}

#[repr(C)]
#[derive(Default)]
struct NativeTimespec {
    seconds: i64,
    nanoseconds: i64,
}

const _: () = {
    assert!(size_of::<NativeIocb>() == 64 && align_of::<NativeIocb>() == 8);
    assert!(offset_of!(NativeIocb, key) == 8);
    assert!(offset_of!(NativeIocb, opcode) == 16);
    assert!(offset_of!(NativeIocb, descriptor) == 20);
    assert!(offset_of!(NativeIocb, buffer) == 24);
    assert!(offset_of!(NativeIocb, offset) == 40);
    assert!(offset_of!(NativeIocb, flags) == 56);
    assert!(size_of::<NativeIoEvent>() == 32 && align_of::<NativeIoEvent>() == 8);
    assert!(offset_of!(NativeIoEvent, result) == 16);
    assert!(size_of::<NativeTimespec>() == 16 && align_of::<NativeTimespec>() == 8);
};

/// One submission identity within the context that produced it.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct AioRequestId {
    context: u64,
    sequence: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct AioFsyncEvent {
    pub request: AioRequestId,
    pub outcome: Result<(), SyscallError>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct AioPipePollEvent {
    pub request: AioRequestId,
    pub outcome: Result<(), SyscallError>,
}

#[derive(Clone, Copy, Eq, PartialEq)]
enum Profile {
    Fsync,
    PipePoll,
}

enum PendingWork {
    Fsync,
    PipePoll { _reader: LinuxFd, _writer: LinuxFd },
}

impl PendingWork {
    fn profile(&self) -> Profile {
        match self {
            Self::Fsync => Profile::Fsync,
            Self::PipePoll { .. } => Profile::PipePoll,
        }
    }
}

struct PendingRequest {
    request: AioRequestId,
    control: Box<NativeIocb>,
    work: PendingWork,
}

/// Exclusive owner of a kernel AIO context. Kernel handles and buffer pointers
/// remain internal. Use the owner in the process that created the context.
pub struct LegacyAioContext {
    handle: Option<NonZeroUsize>,
    identity: u64,
    capacity: usize,
    pending: Vec<PendingRequest>,
    next_request: u64,
    poisoned: bool,
}

impl fmt::Debug for LegacyAioContext {
    fn fmt(&self, output: &mut fmt::Formatter<'_>) -> fmt::Result {
        output
            .debug_struct("LegacyAioContext")
            .field("live", &self.handle.is_some())
            .field("capacity", &self.capacity)
            .field("outstanding", &self.pending.len())
            .field("poisoned", &self.poisoned)
            .finish()
    }
}

impl LegacyAioContext {
    fn usable_handle(&self) -> Result<usize, SyscallError> {
        if self.poisoned {
            return Err(SyscallError::InvalidInput(
                "AIO context needs destruction after an unexpected kernel result",
            ));
        }
        self.handle
            .map(NonZeroUsize::get)
            .ok_or(SyscallError::InvalidInput("AIO context is destroyed"))
    }

    fn ensure_profile(&self, profile: Profile) -> Result<(), SyscallError> {
        if self
            .pending
            .first()
            .is_some_and(|pending| pending.work.profile() != profile)
        {
            return Err(SyscallError::InvalidInput(
                "reap outstanding AIO requests before changing queue profile",
            ));
        }
        Ok(())
    }

    fn unexpected<T>(&mut self, raw: isize) -> Result<T, SyscallError> {
        self.poisoned = true;
        Err(SyscallError::UnexpectedReturn(raw))
    }
}

/// Creates an owned AIO context with a package limit of 1..=16 requests.
pub fn io_setup(entries: u32) -> Result<LegacyAioContext, SyscallError> {
    if !(1..=MAX_AIO_ENTRIES).contains(&entries) {
        return Err(SyscallError::InvalidInput(
            "AIO context capacity must be in 1..=16",
        ));
    }
    let identity = NEXT_CONTEXT
        .fetch_update(Ordering::Relaxed, Ordering::Relaxed, |identity| {
            identity.checked_add(1)
        })
        .map_err(|_| SyscallError::InvalidInput("AIO context identity range is exhausted"))?;
    let mut handle = 0_usize;
    let raw = unsafe {
        abi::call(
            IO_SETUP,
            [
                entries as usize,
                (&mut handle as *mut usize) as usize,
                0,
                0,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)?;
    let handle = NonZeroUsize::new(handle).ok_or(SyscallError::UnexpectedReturn(raw))?;
    Ok(LegacyAioContext {
        handle: Some(handle),
        identity,
        capacity: entries as usize,
        pending: Vec::with_capacity(entries as usize),
        next_request: 1,
        poisoned: false,
    })
}

/// Destroys the context, waiting for outstanding requests as required by
/// Linux. A kernel error preserves the owner for diagnosis or retry.
pub fn io_destroy(context: &mut LegacyAioContext) -> Result<(), SyscallError> {
    let handle = context
        .handle
        .ok_or(SyscallError::InvalidInput("AIO context is destroyed"))?;
    decode_zero(unsafe { abi::call(IO_DESTROY, [handle.get(), 0, 0, 0, 0, 0]) })?;
    context.handle = None;
    context.pending.clear();
    Ok(())
}

impl Drop for LegacyAioContext {
    fn drop(&mut self) {
        if self.handle.is_some() {
            let _ = io_destroy(self);
        }
    }
}

/// Submits one fsync request with no asynchronous user buffer. Linux takes
/// its own file reference during submission. The owned control block remains
/// stable until its completion is reaped or the context is destroyed.
pub fn io_submit_fsync(
    context: &mut LegacyAioContext,
    fd: BorrowedFd<'_>,
) -> Result<AioRequestId, SyscallError> {
    submit(context, Profile::Fsync, || {
        Ok((fd.as_raw_fd() as u32, PendingWork::Fsync))
    })
}

/// Queues readable polling on a new empty private pipe. The pending request
/// owns both endpoints, so ordinary readiness and hangup cannot race cancel.
/// Use the pipe-poll reaper for completions until this queue is empty.
pub fn io_submit_cancellable_pipe_poll(
    context: &mut LegacyAioContext,
) -> Result<AioRequestId, SyscallError> {
    submit(context, Profile::PipePoll, || {
        let (reader, writer) = pipe2(0)?;
        Ok((
            reader.as_raw_fd() as u32,
            PendingWork::PipePoll {
                _reader: reader,
                _writer: writer,
            },
        ))
    })
}

fn submit(
    context: &mut LegacyAioContext,
    profile: Profile,
    prepare: impl FnOnce() -> Result<(u32, PendingWork), SyscallError>,
) -> Result<AioRequestId, SyscallError> {
    let handle = context.usable_handle()?;
    context.ensure_profile(profile)?;
    if context.pending.len() >= context.capacity {
        return Err(SyscallError::InvalidInput(
            "AIO queue is full; reap completions before submitting",
        ));
    }
    let request = AioRequestId {
        context: context.identity,
        sequence: context.next_request,
    };
    let successor = context
        .next_request
        .checked_add(1)
        .ok_or(SyscallError::InvalidInput(
            "AIO request identity range is exhausted",
        ))?;
    let (descriptor, work) = prepare()?;
    let (opcode, buffer) = match profile {
        Profile::Fsync => (IOCB_CMD_FSYNC, 0),
        Profile::PipePoll => (IOCB_CMD_POLL, POLLIN),
    };
    let mut control = Box::new(NativeIocb {
        data: request.sequence,
        opcode,
        descriptor,
        buffer,
        ..NativeIocb::default()
    });
    let mut pointer: *mut NativeIocb = &mut *control;
    let raw = unsafe {
        abi::call(
            IO_SUBMIT,
            [
                handle,
                1,
                (&mut pointer as *mut *mut NativeIocb) as usize,
                0,
                0,
                0,
            ],
        )
    };
    match decode_nonnegative(raw) {
        Ok(1) => {
            context.pending.push(PendingRequest {
                request,
                control,
                work,
            });
            context.next_request = successor;
            Ok(request)
        }
        Err(error @ SyscallError::Kernel(_)) => Err(error),
        _ => {
            context.pending.push(PendingRequest {
                request,
                control,
                work,
            });
            context.unexpected(raw)
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum AioCancelStatus {
    /// Linux reports cancellation in progress. The completion still arrives through the queue.
    CompletionPending,
}

/// Attempts native cancellation of a live request belonging to this context.
/// Linux queues a completion for the cancelled private-pipe poll and reports
/// EINPROGRESS. An FSYNC request retains its original completion and returns
/// EINVAL from cancellation on Linux v6.12.
pub fn io_cancel(
    context: &mut LegacyAioContext,
    request: AioRequestId,
) -> Result<AioCancelStatus, SyscallError> {
    let handle = context.usable_handle()?;
    let pending = context
        .pending
        .iter()
        .find(|pending| pending.request == request)
        .ok_or(SyscallError::InvalidInput(
            "AIO request is not live in this context",
        ))?;
    let control = (&*pending.control as *const NativeIocb) as usize;
    // Linux reads the submission key from the original control block. Its
    // completion is published to the same ring used by the reap operations.
    let raw = unsafe { abi::call(IO_CANCEL, [handle, control, 0, 0, 0, 0]) };
    if raw == -EINPROGRESS {
        return Ok(AioCancelStatus::CompletionPending);
    }
    match decode_nonnegative(raw) {
        Err(error @ SyscallError::Kernel(_)) => Err(error),
        _ => context.unexpected(raw),
    }
}

/// Reaps an available completion prefix with a zero relative timeout.
pub fn io_getevents(context: &mut LegacyAioContext) -> Result<Vec<AioFsyncEvent>, SyscallError> {
    reap_fsync(IO_GETEVENTS, context)
}

/// Reaps an available completion prefix with a zero relative timeout and
/// leaves the calling thread's signal mask as supplied by the caller.
pub fn io_pgetevents(context: &mut LegacyAioContext) -> Result<Vec<AioFsyncEvent>, SyscallError> {
    reap_fsync(IO_PGETEVENTS, context)
}

/// Reaps available private-pipe poll completions. A zero outcome means the
/// kernel completed a cancelled poll with an empty readiness mask.
pub fn io_getevents_cancelled_pipe_poll(
    context: &mut LegacyAioContext,
) -> Result<Vec<AioPipePollEvent>, SyscallError> {
    reap(
        IO_GETEVENTS,
        context,
        Profile::PipePoll,
        |request, outcome| AioPipePollEvent { request, outcome },
    )
}

fn reap_fsync(
    number: usize,
    context: &mut LegacyAioContext,
) -> Result<Vec<AioFsyncEvent>, SyscallError> {
    reap(number, context, Profile::Fsync, |request, outcome| {
        AioFsyncEvent { request, outcome }
    })
}

fn reap<T>(
    number: usize,
    context: &mut LegacyAioContext,
    profile: Profile,
    event_from: impl Fn(AioRequestId, Result<(), SyscallError>) -> T,
) -> Result<Vec<T>, SyscallError> {
    let handle = context.usable_handle()?;
    context.ensure_profile(profile)?;
    let timeout = NativeTimespec::default();
    let mut events = [NativeIoEvent::default(); MAX_AIO_ENTRIES as usize];
    let raw = unsafe {
        abi::call(
            number,
            [
                handle,
                0,
                context.capacity,
                events.as_mut_ptr() as usize,
                (&timeout as *const NativeTimespec) as usize,
                0,
            ],
        )
    };
    let count = match decode_nonnegative(raw) {
        Ok(count) if count <= context.pending.len() => count,
        Err(error @ SyscallError::Kernel(_)) => return Err(error),
        _ => return context.unexpected(raw),
    };
    let mut results = Vec::with_capacity(count);
    for (index, event) in events[..count].iter().enumerate() {
        let request = AioRequestId {
            context: context.identity,
            sequence: event.data,
        };
        let object_matches = context.pending.iter().any(|pending| {
            pending.request == request
                && (&*pending.control as *const NativeIocb) as u64 == event.object
        });
        if event.secondary_result != 0
            || !object_matches
            || events[..index]
                .iter()
                .any(|previous| previous.data == event.data)
        {
            return context.unexpected(raw);
        }
        results.push(event_from(request, decode_zero(event.result as isize)));
    }
    context.pending.retain(|pending| {
        !events[..count]
            .iter()
            .any(|event| event.data == pending.request.sequence)
    });
    Ok(results)
}
