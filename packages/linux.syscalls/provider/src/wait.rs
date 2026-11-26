use super::{abi, decode_write, decode_zero, LinuxFd, SyscallError};
use std::os::fd::{AsRawFd, BorrowedFd};

pub const POLLIN: i16 = 0x001;
pub const POLLPRI: i16 = 0x002;
pub const POLLOUT: i16 = 0x004;
pub const POLLERR: i16 = 0x008;
pub const POLLHUP: i16 = 0x010;
pub const POLLNVAL: i16 = 0x020;
pub const CLOCK_REALTIME: i32 = 0;
pub const CLOCK_MONOTONIC: i32 = 1;
pub const EFD_SEMAPHORE: i32 = 1;

#[derive(Debug)]
pub struct PollEntry<'a> {
    fd: BorrowedFd<'a>,
    events: i16,
    returned: i16,
}

impl<'a> PollEntry<'a> {
    pub fn new(fd: BorrowedFd<'a>, events: i16) -> Self {
        Self {
            fd,
            events,
            returned: 0,
        }
    }

    pub fn returned(&self) -> i16 {
        self.returned
    }
}

#[repr(C)]
struct PollFd {
    fd: i32,
    events: i16,
    revents: i16,
}

/// A zero return means timeout, including a nonblocking probe with timeout 0.
/// On error the public entries retain their previous returned events.
pub fn poll(entries: &mut [PollEntry<'_>], timeout_ms: i32) -> Result<usize, SyscallError> {
    poll_with(entries, |address, count| unsafe {
        abi::invoke(abi::POLL, [address, count, timeout_ms as usize, 0, 0, 0])
    })
}

/// Invoke a poll ABI operation with an array of native poll descriptors.
pub(super) fn poll_with(
    entries: &mut [PollEntry<'_>],
    invoke: impl FnOnce(usize, usize) -> isize,
) -> Result<usize, SyscallError> {
    let mut native: Vec<PollFd> = entries
        .iter()
        .map(|entry| PollFd {
            fd: entry.fd.as_raw_fd(),
            events: entry.events,
            revents: 0,
        })
        .collect();
    let raw = invoke(native.as_mut_ptr() as usize, native.len());
    let ready = decode_write(raw, entries.len())?;
    for (entry, returned) in entries.iter_mut().zip(native) {
        entry.returned = returned.revents;
    }
    Ok(ready)
}

#[repr(C)]
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct Timespec {
    seconds: i64,
    nanos: i64,
}

impl Timespec {
    pub fn new(seconds: i64, nanos: i64) -> Result<Self, SyscallError> {
        if !(0..1_000_000_000).contains(&nanos) {
            return Err(SyscallError::InvalidInput(
                "nanoseconds outside 0..1_000_000_000",
            ));
        }
        Ok(Self { seconds, nanos })
    }

    pub fn seconds(self) -> i64 {
        self.seconds
    }

    pub fn nanos(self) -> i64 {
        self.nanos
    }

    pub(super) fn checked(self, raw: isize) -> Result<Self, SyscallError> {
        Self::new(self.seconds, self.nanos).map_err(|_| SyscallError::UnexpectedReturn(raw))
    }
}

pub fn clock_gettime(clock: i32) -> Result<Timespec, SyscallError> {
    read_clock(abi::CLOCK_GETTIME, clock)
}

pub(super) fn read_clock(operation: usize, clock: i32) -> Result<Timespec, SyscallError> {
    let mut result = Timespec::default();
    let raw = unsafe {
        abi::invoke(
            operation,
            [
                clock as usize,
                (&mut result as *mut Timespec) as usize,
                0,
                0,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)?;
    result.checked(raw)
}

/// Returns an owned Linux eventfd with the supplied flags.
pub fn eventfd2(initial: u32, flags: i32) -> Result<LinuxFd, SyscallError> {
    let raw = unsafe {
        abi::invoke(
            abi::EVENTFD2,
            [initial as usize, flags as usize, 0, 0, 0, 0],
        )
    };
    LinuxFd::from_result(raw)
}
