use super::{
    abi, decode_nonnegative, decode_zero, LinuxFd, PollEntry, SyscallError, Timespec, EINTR,
};
use std::ptr;

const PIPE: usize = 22;
const GETTIMEOFDAY: usize = 96;
const TIME: usize = 201;
const EPOLL_CREATE: usize = 213;
const CLOCK_NANOSLEEP: usize = 230;
const PPOLL: usize = 271;
const EVENTFD: usize = 284;

/// Returns owned read and write endpoints in this order, without FD_CLOEXEC.
/// Use `pipe2` to set FD_CLOEXEC atomically.
pub fn pipe() -> Result<(LinuxFd, LinuxFd), SyscallError> {
    let mut descriptors = [-1_i32; 2];
    let raw = unsafe { abi::invoke(PIPE, [descriptors.as_mut_ptr() as usize, 0, 0, 0, 0, 0]) };
    super::fd::decode_pipe(raw, descriptors)
}

/// Returns an owned, blocking, non-semaphore event descriptor without FD_CLOEXEC.
/// Use `eventfd2` to set FD_CLOEXEC atomically.
pub fn eventfd(initial: u32) -> Result<LinuxFd, SyscallError> {
    let raw = unsafe { abi::invoke(EVENTFD, [initial as usize, 0, 0, 0, 0, 0]) };
    LinuxFd::from_result(raw)
}

/// Returns an owned epoll descriptor without FD_CLOEXEC. Linux requires a
/// positive size hint, though it determines the internal capacity itself.
pub fn epoll_create(size_hint: i32) -> Result<LinuxFd, SyscallError> {
    let raw = unsafe { abi::invoke(EPOLL_CREATE, [size_hint as usize, 0, 0, 0, 0, 0]) };
    LinuxFd::from_result(raw)
}

#[repr(C)]
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct Timeval {
    seconds: i64,
    micros: i64,
}

impl Timeval {
    /// Construct an epoch timestamp with a normalized microsecond field.
    pub fn new(seconds: i64, micros: i64) -> Result<Self, SyscallError> {
        if !(0..1_000_000).contains(&micros) {
            return Err(SyscallError::InvalidInput(
                "microseconds outside 0..1_000_000",
            ));
        }
        Ok(Self { seconds, micros })
    }

    pub fn seconds(self) -> i64 {
        self.seconds
    }

    pub fn micros(self) -> i64 {
        self.micros
    }
}

/// Reads wall-clock time as seconds since the Unix epoch and a microsecond component.
/// Does not request the obsolete timezone output.
pub fn gettimeofday() -> Result<Timeval, SyscallError> {
    let mut result = Timeval::default();
    let raw = unsafe {
        abi::invoke(
            GETTIMEOFDAY,
            [ptr::from_mut(&mut result) as usize, 0, 0, 0, 0, 0],
        )
    };
    decode_zero(raw)?;
    Timeval::new(result.seconds, result.micros).map_err(|_| SyscallError::UnexpectedReturn(raw))
}

/// Reads whole signed seconds since the Unix epoch. Linux reports a successful
/// timestamp both as the raw return value and through the output address. The
/// output distinguishes even a negative pre-epoch timestamp from an errno.
pub fn time() -> Result<i64, SyscallError> {
    const UNWRITTEN: i64 = i64::MIN;
    let mut seconds = UNWRITTEN;
    let raw = unsafe { abi::invoke(TIME, [ptr::from_mut(&mut seconds) as usize, 0, 0, 0, 0, 0]) };
    if seconds == UNWRITTEN {
        decode_nonnegative(raw)?;
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    if raw as i64 != seconds {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    Ok(seconds)
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(i32)]
pub enum ClockSleepMode {
    Relative = 0,
    Absolute = 1,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ClockSleepOutcome {
    Completed,
    Interrupted { remaining: Option<Timespec> },
}

/// Sleeps once relative to a clock or until an absolute deadline. Relative
/// interruption exposes the unslept duration. Absolute interruption leaves the
/// original deadline usable for a subsequent call.
pub fn clock_nanosleep(
    clock: i32,
    mode: ClockSleepMode,
    request: Timespec,
) -> Result<ClockSleepOutcome, SyscallError> {
    let mut remaining = Timespec::default();
    let remaining_ptr = match mode {
        ClockSleepMode::Relative => ptr::from_mut(&mut remaining),
        ClockSleepMode::Absolute => ptr::null_mut(),
    };
    let raw = unsafe {
        abi::invoke(
            CLOCK_NANOSLEEP,
            [
                clock as usize,
                mode as usize,
                ptr::from_ref(&request) as usize,
                remaining_ptr as usize,
                0,
                0,
            ],
        )
    };
    if raw == -(EINTR as isize) {
        let remaining = match mode {
            ClockSleepMode::Relative => Some(remaining.checked(raw)?),
            ClockSleepMode::Absolute => None,
        };
        return Ok(ClockSleepOutcome::Interrupted { remaining });
    }
    decode_zero(raw)?;
    Ok(ClockSleepOutcome::Completed)
}

/// Checks readiness with an optional relative nanosecond-resolution timeout.
/// This profile leaves the signal mask unchanged. Linux may modify its copy of
/// the timeout. Caller entries keep their previous results on error.
pub fn ppoll(
    entries: &mut [PollEntry<'_>],
    mut timeout: Option<Timespec>,
) -> Result<usize, SyscallError> {
    let timeout_ptr = timeout.as_mut().map_or(ptr::null_mut(), ptr::from_mut);
    super::wait::poll_with(entries, |address, count| unsafe {
        abi::invoke(PPOLL, [address, count, timeout_ptr as usize, 0, 0, 0])
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::mem::{align_of, offset_of, size_of};

    #[test]
    fn timeval_matches_linux_x86_64_layout() {
        assert_eq!(size_of::<Timeval>(), 16);
        assert_eq!(align_of::<Timeval>(), 8);
        assert_eq!(offset_of!(Timeval, micros), 8);
    }
}
