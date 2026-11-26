//! Current-thread signal masks and signalfd for explicitly routed user signals.

use super::{
    abi, close, decode_zero, read, LinuxFd, ReadOutcome, SyscallError, O_CLOEXEC, O_NONBLOCK,
};
use std::fmt;
use std::marker::PhantomData;
use std::mem::size_of;
use std::os::fd::{AsFd, BorrowedFd};
use std::ptr;
use std::rc::Rc;

pub(super) const RT_SIGPROCMASK: usize = 14;
pub(super) const RT_SIGPENDING: usize = 127;
const SIGNALFD: usize = 282;
const SIGNALFD4: usize = 289;
const SIG_BLOCK: usize = 0;
const SIG_UNBLOCK: usize = 1;
const SIG_SETMASK: usize = 2;
const NATIVE_SIGNAL_MASK_BYTES: usize = size_of::<u64>();
const SIGNAL_RECORD_BYTES: usize = 128;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u32)]
pub enum UserSignal {
    User1 = 10,
    User2 = 12,
}

impl UserSignal {
    const fn bit(self) -> u64 {
        1_u64 << (self as u32 - 1)
    }
}

/// Standard user signals supported by this native profile.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct UserSignals(u64);

impl UserSignals {
    pub const USER1: Self = Self(UserSignal::User1.bit());
    pub const USER2: Self = Self(UserSignal::User2.bit());
    pub const BOTH: Self = Self(Self::USER1.0 | Self::USER2.0);
}

/// The current-thread scope passed to the callback after mask setup succeeds.
/// The scope and its signal descriptors cannot be sent to another thread.
#[derive(Debug)]
pub struct CurrentThreadSignalScope {
    signals: UserSignals,
    thread_bound: PhantomData<Rc<()>>,
}

impl CurrentThreadSignalScope {
    pub(super) fn mask(&self) -> u64 {
        self.signals.0
    }

    pub(super) fn permits(&self, signal: UserSignal) -> bool {
        signal.bit() & self.signals.0 != 0
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SignalScopeError {
    Setup(SyscallError),
    Restore(SyscallError),
}

impl fmt::Display for SignalScopeError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Setup(error) => write!(formatter, "block current-thread signals: {error}"),
            Self::Restore(error) => {
                write!(formatter, "restore current-thread signal mask: {error}")
            }
        }
    }
}

impl std::error::Error for SignalScopeError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Setup(error) | Self::Restore(error) => Some(error),
        }
    }
}

struct MaskRestoration {
    newly_blocked: u64,
}

impl MaskRestoration {
    fn restore(&mut self) -> Result<(), SyscallError> {
        let newly_blocked = std::mem::take(&mut self.newly_blocked);
        if newly_blocked == 0 {
            return Ok(());
        }
        change_mask(SIG_UNBLOCK, &newly_blocked, ptr::null_mut())
    }
}

impl Drop for MaskRestoration {
    fn drop(&mut self) {
        let _ = self.restore();
    }
}

fn change_mask(how: usize, mask: &u64, previous: *mut u64) -> Result<(), SyscallError> {
    let raw = unsafe {
        abi::call(
            RT_SIGPROCMASK,
            [
                how,
                ptr::from_ref(mask) as usize,
                previous as usize,
                NATIVE_SIGNAL_MASK_BYTES,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)
}

pub(super) fn replace_mask(mask: u64, previous: Option<&mut u64>) -> Result<(), SyscallError> {
    change_mask(
        SIG_SETMASK,
        &mask,
        previous.map_or(ptr::null_mut(), ptr::from_mut),
    )
}

/// Blocks a set of user signals on the calling thread while running `body`.
/// Only bits newly blocked here are unblocked on return, preserving outer scopes.
/// A normal restoration failure is reported. Unwinding attempts restoration once.
///
/// The caller coordinates delivery and consumption. In particular, pending
/// signals can take their usual action, including process termination, when
/// unblocked. Route only signals intended for this scope and handle any pending
/// signals before leaving it. Process-directed signals can reach other threads.
///
/// ```compile_fail
/// use linux_syscalls_provider::{rt_sigprocmask, signalfd4, UserSignals};
/// let escaped = rt_sigprocmask(UserSignals::USER1, |scope| signalfd4(scope).unwrap());
/// ```
pub fn rt_sigprocmask<T>(
    signals: UserSignals,
    body: impl for<'scope> FnOnce(&'scope CurrentThreadSignalScope) -> T,
) -> Result<T, SignalScopeError> {
    let mut previous = 0_u64;
    change_mask(SIG_BLOCK, &signals.0, ptr::from_mut(&mut previous))
        .map_err(SignalScopeError::Setup)?;
    let mut restoration = MaskRestoration {
        newly_blocked: signals.0 & !previous,
    };
    let scope = CurrentThreadSignalScope {
        signals,
        thread_bound: PhantomData,
    };
    let result = body(&scope);
    restoration.restore().map_err(SignalScopeError::Restore)?;
    Ok(result)
}

/// An owned, nonblocking Linux signalfd bound to a current-thread mask scope.
///
/// ```compile_fail
/// use linux_syscalls_provider::{rt_sigprocmask, signalfd4, UserSignals};
/// rt_sigprocmask(UserSignals::USER1, |scope| {
///     let fd = signalfd4(scope).unwrap();
///     std::thread::scope(|worker| worker.spawn(move || drop(fd)).join().unwrap());
/// }).unwrap();
/// ```
#[derive(Debug)]
pub struct SignalFd<'scope>(ScopedSignalDescriptor<'scope>);

/// An owned, initially blocking legacy signalfd. FD_CLOEXEC is clear after
/// creation. The descriptor borrows the current-thread mask scope.
#[derive(Debug)]
pub struct BlockingSignalFd<'scope>(ScopedSignalDescriptor<'scope>);

#[derive(Debug)]
struct ScopedSignalDescriptor<'scope> {
    descriptor: LinuxFd,
    scope: &'scope CurrentThreadSignalScope,
}

impl AsFd for SignalFd<'_> {
    fn as_fd(&self) -> BorrowedFd<'_> {
        self.0.descriptor.as_fd()
    }
}

impl AsFd for BlockingSignalFd<'_> {
    fn as_fd(&self) -> BorrowedFd<'_> {
        self.0.descriptor.as_fd()
    }
}

impl SignalFd<'_> {
    pub fn close(self) -> Result<(), SyscallError> {
        close(self.0.descriptor)
    }
}

impl BlockingSignalFd<'_> {
    pub fn close(self) -> Result<(), SyscallError> {
        close(self.0.descriptor)
    }
}

/// Reads and decodes exactly one pending record. An empty nonblocking
/// descriptor propagates Linux EAGAIN. Sender metadata comes from Linux.
pub fn signalfd_read(fd: &SignalFd<'_>) -> Result<SignalEvent, SyscallError> {
    read_signal_event(&fd.0)
}

/// Reads and decodes exactly one record from a legacy signalfd. An empty
/// descriptor may block. Interruption returns EINTR without a retry.
pub fn signalfd_read_blocking(fd: &BlockingSignalFd<'_>) -> Result<SignalEvent, SyscallError> {
    read_signal_event(&fd.0)
}

fn read_signal_event(fd: &ScopedSignalDescriptor<'_>) -> Result<SignalEvent, SyscallError> {
    let mut bytes = [0_u8; SIGNAL_RECORD_BYTES];
    let count = match read(fd.descriptor.as_fd(), &mut bytes)? {
        ReadOutcome::Progress(count) => count,
        ReadOutcome::Eof => return Err(SyscallError::UnexpectedReturn(0)),
    };
    if count != bytes.len() {
        return Err(SyscallError::UnexpectedReturn(count as isize));
    }
    let signo = u32::from_ne_bytes(bytes[0..4].try_into().expect("four-byte field"));
    let signal = match signo {
        value if value == UserSignal::User1 as u32 => UserSignal::User1,
        value if value == UserSignal::User2 as u32 => UserSignal::User2,
        _ => return Err(SyscallError::UnexpectedReturn(count as isize)),
    };
    if !fd.scope.permits(signal) {
        return Err(SyscallError::UnexpectedReturn(count as isize));
    }
    Ok(SignalEvent {
        signal,
        code: i32::from_ne_bytes(bytes[8..12].try_into().expect("four-byte field")),
        pid: u32::from_ne_bytes(bytes[12..16].try_into().expect("four-byte field")),
        uid: u32::from_ne_bytes(bytes[16..20].try_into().expect("four-byte field")),
    })
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct SignalEvent {
    pub signal: UserSignal,
    pub code: i32,
    pub pid: u32,
    pub uid: u32,
}

/// Creates one signal descriptor for this scope, with O_NONBLOCK and FD_CLOEXEC.
pub fn signalfd4(scope: &CurrentThreadSignalScope) -> Result<SignalFd<'_>, SyscallError> {
    create_signal_descriptor(scope, SIGNALFD4, (O_NONBLOCK | O_CLOEXEC) as usize).map(SignalFd)
}

/// Creates a legacy signal descriptor for this scope without O_NONBLOCK or
/// FD_CLOEXEC. Close the descriptor before an exec when inheritance is unwanted.
pub fn signalfd(scope: &CurrentThreadSignalScope) -> Result<BlockingSignalFd<'_>, SyscallError> {
    create_signal_descriptor(scope, SIGNALFD, 0).map(BlockingSignalFd)
}

fn create_signal_descriptor(
    scope: &CurrentThreadSignalScope,
    operation: usize,
    flags: usize,
) -> Result<ScopedSignalDescriptor<'_>, SyscallError> {
    let raw = unsafe {
        abi::call(
            operation,
            [
                (-1_i32) as usize,
                ptr::from_ref(&scope.signals.0) as usize,
                NATIVE_SIGNAL_MASK_BYTES,
                flags,
                0,
                0,
            ],
        )
    };
    Ok(ScopedSignalDescriptor {
        descriptor: LinuxFd::from_result(raw)?,
        scope,
    })
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct PendingUserSignals {
    pub user1: bool,
    pub user2: bool,
}

/// Queries pending signals visible to the calling thread and reports only the
/// blocked user signals selected by the scope. It does not consume a pending
/// signal or change the thread's mask. Process-shared pending signals may be
/// visible even when they were not directed to this thread.
pub fn rt_sigpending(scope: &CurrentThreadSignalScope) -> Result<PendingUserSignals, SyscallError> {
    let mut pending = 0_u64;
    let raw = unsafe {
        abi::call(
            RT_SIGPENDING,
            [
                ptr::from_mut(&mut pending) as usize,
                NATIVE_SIGNAL_MASK_BYTES,
                0,
                0,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)?;
    let selected = pending & scope.signals.0;
    Ok(PendingUserSignals {
        user1: selected & UserSignal::User1.bit() != 0,
        user2: selected & UserSignal::User2.bit() != 0,
    })
}
