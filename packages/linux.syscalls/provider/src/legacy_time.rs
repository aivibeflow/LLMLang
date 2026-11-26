//! Process interval timers and CPU accounting for the native Linux x86-64 ABI.

use super::{abi, decode_nonnegative, decode_zero, SyscallError};
use std::mem::{align_of, offset_of, size_of};
use std::ptr;

pub(super) const GETITIMER: usize = 36;
const ALARM: usize = 37;
pub(super) const SETITIMER: usize = 38;
const TIMES: usize = 100;

/// Selects a process-wide timer. The kernel associates Real, Virtual, and
/// Profile expiration with SIGALRM, SIGVTALRM, and SIGPROF respectively.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(i32)]
pub enum IntervalTimer {
    Real = 0,
    Virtual = 1,
    Profile = 2,
}

/// A nonnegative duration in the native Linux timeval representation.
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
#[repr(C)]
pub struct IntervalDuration {
    seconds: i64,
    micros: i64,
}

impl IntervalDuration {
    pub fn new(seconds: i64, micros: i64) -> Result<Self, SyscallError> {
        if seconds < 0 || !(0..1_000_000).contains(&micros) {
            return Err(SyscallError::InvalidInput(
                "invalid interval timer duration",
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

    fn checked(self, raw: isize) -> Result<Self, SyscallError> {
        Self::new(self.seconds, self.micros).map_err(|_| SyscallError::UnexpectedReturn(raw))
    }
}

/// Native itimerval layout. A zero `remaining` disarms the selected timer
/// when used as the input. A zero `interval` requests one-shot behavior.
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
#[repr(C)]
pub struct IntervalSettings {
    pub interval: IntervalDuration,
    pub remaining: IntervalDuration,
}

impl IntervalSettings {
    fn checked(self, raw: isize) -> Result<Self, SyscallError> {
        decode_zero(raw)?;
        Ok(Self {
            interval: self.interval.checked(raw)?,
            remaining: self.remaining.checked(raw)?,
        })
    }
}

/// Reads the interval and remaining time of the selected process timer.
pub fn getitimer(which: IntervalTimer) -> Result<IntervalSettings, SyscallError> {
    let mut result = IntervalSettings::default();
    let raw = unsafe {
        abi::call(
            GETITIMER,
            [
                which as usize,
                ptr::from_mut(&mut result) as usize,
                0,
                0,
                0,
                0,
            ],
        )
    };
    result.checked(raw)
}

/// Changes the selected process-wide timer and returns its previous settings.
/// The caller coordinates shared timer state and the disposition or mask for
/// its expiration signal, which can terminate the process by default.
pub fn setitimer(
    which: IntervalTimer,
    new: IntervalSettings,
) -> Result<IntervalSettings, SyscallError> {
    let mut previous = IntervalSettings::default();
    let raw = unsafe {
        abi::call(
            SETITIMER,
            [
                which as usize,
                ptr::from_ref(&new) as usize,
                ptr::from_mut(&mut previous) as usize,
                0,
                0,
                0,
            ],
        )
    };
    previous.checked(raw)
}

/// Replaces the process's ITIMER_REAL setting and returns the old remaining
/// time rounded by Linux. Passing zero cancels the timer. The caller coordinates
/// the shared timer and the SIGALRM disposition or mask before scheduling.
pub fn alarm(seconds: u32) -> Result<u32, SyscallError> {
    let raw = unsafe { abi::call(ALARM, [seconds as usize, 0, 0, 0, 0, 0]) };
    u32::try_from(decode_nonnegative(raw)?).map_err(|_| SyscallError::UnexpectedReturn(raw))
}

#[repr(C)]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct NativeTimes {
    user: i64,
    system: i64,
    children_user: i64,
    children_system: i64,
}

const _: () = {
    assert!(size_of::<IntervalDuration>() == 16);
    assert!(align_of::<IntervalDuration>() == 8);
    assert!(offset_of!(IntervalDuration, micros) == 8);
    assert!(size_of::<IntervalSettings>() == 32);
    assert!(offset_of!(IntervalSettings, remaining) == 16);
    assert!(size_of::<NativeTimes>() == 32);
    assert!(align_of::<NativeTimes>() == 8);
    assert!(offset_of!(NativeTimes, system) == 8);
    assert!(offset_of!(NativeTimes, children_user) == 16);
    assert!(offset_of!(NativeTimes, children_system) == 24);
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ProcessTimes {
    pub elapsed: i64,
    pub user: i64,
    pub system: i64,
    pub children_user: i64,
    pub children_system: i64,
}

/// Reads process and waited-for child CPU ticks. `elapsed` is the kernel's
/// signed clock tick count from an arbitrary origin and may wrap. Supplying
/// an output record lets us distinguish success from a negative Linux errno.
pub fn times() -> Result<ProcessTimes, SyscallError> {
    let mut result = UNWRITTEN;
    let raw = unsafe { abi::call(TIMES, [ptr::from_mut(&mut result) as usize, 0, 0, 0, 0, 0]) };
    decode_times(raw, result)
}

const UNWRITTEN: NativeTimes = NativeTimes {
    user: i64::MIN,
    system: i64::MIN,
    children_user: i64::MIN,
    children_system: i64::MIN,
};

fn decode_times(raw: isize, result: NativeTimes) -> Result<ProcessTimes, SyscallError> {
    if result == UNWRITTEN {
        decode_nonnegative(raw)?;
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    Ok(ProcessTimes {
        elapsed: raw as i64,
        user: result.user,
        system: result.system,
        children_user: result.children_user,
        children_system: result.children_system,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::EINTR;

    #[test]
    fn native_times_distinguishes_signed_success_from_errno() {
        let raw = -(EINTR as isize);
        let written = NativeTimes {
            user: 2,
            system: 1,
            children_user: 0,
            children_system: 0,
        };
        let success = decode_times(raw, written).unwrap();
        assert_eq!(success.elapsed, raw as i64);
        assert_eq!(success.user, 2);
        assert!(decode_times(raw, UNWRITTEN).unwrap_err().is_errno(EINTR));
    }
}
