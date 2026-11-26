use super::{abi, decode_write, decode_zero, LinuxFd, SyscallError, Timespec, EINTR};
use std::mem::size_of;
use std::os::fd::{AsRawFd, BorrowedFd};
use std::ptr;

#[repr(C)]
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct TimerSpec {
    pub interval: Timespec,
    pub initial: Timespec,
}

impl TimerSpec {
    pub(super) fn checked(self, raw: isize) -> Result<Self, SyscallError> {
        self.interval.checked(raw)?;
        self.initial.checked(raw)?;
        Ok(self)
    }
}

const EPOLL_PWAIT: usize = 281;
const EPOLL_PWAIT2: usize = 441;

pub const TFD_TIMER_ABSTIME: i32 = 1;
pub const TFD_TIMER_CANCEL_ON_SET: i32 = 2;
pub const EPOLLIN: u32 = 0x001;
pub const EPOLLOUT: u32 = 0x004;
pub const EPOLLERR: u32 = 0x008;
pub const EPOLLHUP: u32 = 0x010;
pub const EPOLLONESHOT: u32 = 1 << 30;
pub const EPOLLET: u32 = 1 << 31;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SleepOutcome {
    Completed,
    Interrupted { remaining: Timespec },
}

pub fn clock_getres(clock: i32) -> Result<Timespec, SyscallError> {
    super::wait::read_clock(abi::CLOCK_GETRES, clock)
}

/// Performs one relative sleep. On EINTR the caller receives the unslept time.
pub fn nanosleep(request: Timespec) -> Result<SleepOutcome, SyscallError> {
    let mut remaining = Timespec::default();
    let raw = unsafe {
        abi::invoke(
            abi::NANOSLEEP,
            [
                ptr::from_ref(&request) as usize,
                ptr::from_mut(&mut remaining) as usize,
                0,
                0,
                0,
                0,
            ],
        )
    };
    if raw == -(EINTR as isize) {
        return Ok(SleepOutcome::Interrupted {
            remaining: remaining.checked(raw)?,
        });
    }
    decode_zero(raw)?;
    Ok(SleepOutcome::Completed)
}

/// Returns an owned timer descriptor with the supplied flags.
pub fn timerfd_create(clock: i32, flags: i32) -> Result<LinuxFd, SyscallError> {
    LinuxFd::from_result(unsafe {
        abi::invoke(
            abi::TIMERFD_CREATE,
            [clock as usize, flags as usize, 0, 0, 0, 0],
        )
    })
}

/// Updates the timer and returns its previous setting on success.
pub fn timerfd_settime(
    fd: BorrowedFd<'_>,
    flags: i32,
    new: TimerSpec,
) -> Result<TimerSpec, SyscallError> {
    let mut previous = TimerSpec::default();
    let raw = unsafe {
        abi::invoke(
            abi::TIMERFD_SETTIME,
            [
                fd.as_raw_fd() as usize,
                flags as usize,
                ptr::from_ref(&new) as usize,
                ptr::from_mut(&mut previous) as usize,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)?;
    previous.checked(raw)
}

pub fn timerfd_gettime(fd: BorrowedFd<'_>) -> Result<TimerSpec, SyscallError> {
    let mut result = TimerSpec::default();
    let raw = unsafe {
        abi::invoke(
            abi::TIMERFD_GETTIME,
            [
                fd.as_raw_fd() as usize,
                ptr::from_mut(&mut result) as usize,
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

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct EpollEvent {
    pub events: u32,
    pub data: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum EpollControl {
    Add(EpollEvent),
    Modify(EpollEvent),
    Delete,
}

// The native UAPI packs the x86-64 epoll data word at offset 4.
// Keep that representation inside the adapter and copy out unaligned fields by value.
#[repr(C, packed)]
#[derive(Clone, Copy, Default)]
struct NativeEpollEvent {
    events: u32,
    data: u64,
}

impl From<EpollEvent> for NativeEpollEvent {
    fn from(event: EpollEvent) -> Self {
        Self {
            events: event.events,
            data: event.data,
        }
    }
}

impl From<NativeEpollEvent> for EpollEvent {
    fn from(event: NativeEpollEvent) -> Self {
        Self {
            events: event.events,
            data: event.data,
        }
    }
}

/// Returns an owned epoll descriptor with the supplied flags.
pub fn epoll_create1(flags: i32) -> Result<LinuxFd, SyscallError> {
    LinuxFd::from_result(unsafe {
        abi::invoke(
            abi::EPOLL_CREATE1,
            [flags as usize, 0, 0, 0, 0, 0],
        )
    })
}

pub fn epoll_ctl(
    epoll: BorrowedFd<'_>,
    watched: BorrowedFd<'_>,
    change: EpollControl,
) -> Result<(), SyscallError> {
    let (command, event) = match change {
        EpollControl::Add(event) => (1, Some(NativeEpollEvent::from(event))),
        EpollControl::Delete => (2, None),
        EpollControl::Modify(event) => (3, Some(NativeEpollEvent::from(event))),
    };
    let argument = event.as_ref().map_or(ptr::null(), ptr::from_ref);
    decode_zero(unsafe {
        abi::invoke(
            abi::EPOLL_CTL,
            [
                epoll.as_raw_fd() as usize,
                command,
                watched.as_raw_fd() as usize,
                argument as usize,
                0,
                0,
            ],
        )
    })
}

/// Initializes exactly the returned prefix of `events`; the remainder is left unchanged.
/// A zero result means timeout. On error all caller entries remain unchanged.
pub fn epoll_wait(
    epoll: BorrowedFd<'_>,
    events: &mut [EpollEvent],
    timeout_ms: i32,
) -> Result<usize, SyscallError> {
    wait_for_epoll_events(abi::EPOLL_WAIT, epoll, events, timeout_ms as usize)
}

/// Waits with a millisecond timeout without changing the calling thread's
/// signal mask. A negative timeout waits indefinitely, and zero probes readiness.
/// An error leaves all caller event slots unchanged.
pub fn epoll_pwait(
    epoll: BorrowedFd<'_>,
    events: &mut [EpollEvent],
    timeout_ms: i32,
) -> Result<usize, SyscallError> {
    wait_for_epoll_events(EPOLL_PWAIT, epoll, events, timeout_ms as usize)
}

/// Waits with optional relative nanosecond precision. `None` waits indefinitely.
/// The adapter leaves the calling thread's signal mask and unfilled event slots
/// unchanged. The caller receives EINTR if Linux interrupts the wait.
pub fn epoll_pwait2(
    epoll: BorrowedFd<'_>,
    events: &mut [EpollEvent],
    timeout: Option<Timespec>,
) -> Result<usize, SyscallError> {
    let argument = timeout.as_ref().map_or(ptr::null(), ptr::from_ref);
    wait_for_epoll_events(EPOLL_PWAIT2, epoll, events, argument as usize)
}

fn wait_for_epoll_events(
    operation: usize,
    epoll: BorrowedFd<'_>,
    events: &mut [EpollEvent],
    timeout_argument: usize,
) -> Result<usize, SyscallError> {
    let max_events = i32::MAX as usize / size_of::<NativeEpollEvent>();
    if !(1..=max_events).contains(&events.len()) {
        return Err(SyscallError::InvalidInput(
            "epoll_wait slot count outside the Linux limit",
        ));
    }
    let mut native = vec![NativeEpollEvent::default(); events.len()];
    let raw = unsafe {
        abi::invoke(
            operation,
            [
                epoll.as_raw_fd() as usize,
                native.as_mut_ptr() as usize,
                native.len(),
                timeout_argument,
                0,
                0,
            ],
        )
    };
    let count = decode_write(raw, events.len())?;
    for (destination, result) in events.iter_mut().zip(native).take(count) {
        *destination = EpollEvent::from(result);
    }
    Ok(count)
}

#[cfg(test)]
mod layout_tests {
    use super::*;
    use std::mem::{align_of, offset_of, size_of};

    #[test]
    fn native_structures_match_x86_64_uapi() {
        assert_eq!(size_of::<Timespec>(), 16);
        assert_eq!(align_of::<Timespec>(), 8);
        assert_eq!(size_of::<TimerSpec>(), 32);
        assert_eq!(offset_of!(TimerSpec, initial), 16);
        assert_eq!(size_of::<NativeEpollEvent>(), 12);
        assert_eq!(offset_of!(NativeEpollEvent, data), 4);
    }
}
