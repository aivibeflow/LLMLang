//! Owned, process-local POSIX timers with native SIGEV_NONE notification mode.

use super::{abi, decode_nonnegative, decode_zero, SyscallError, TimerSpec};
use std::fmt;
use std::ptr;

const TIMER_CREATE: usize = 222;
const TIMER_SETTIME: usize = 223;
const TIMER_GETTIME: usize = 224;
const TIMER_GETOVERRUN: usize = 225;
const TIMER_DELETE: usize = 226;
const SIGEV_NONE: i32 = 1;

#[repr(C)]
pub(super) struct NativeSignalEvent {
    value: u64,
    signal_number: i32,
    notification: i32,
    reserved: [u8; 48],
}

impl NativeSignalEvent {
    pub(super) fn none() -> Self {
        Self {
            value: 0,
            signal_number: 0,
            notification: SIGEV_NONE,
            reserved: [0; 48],
        }
    }
}

const _: () = {
    assert!(std::mem::size_of::<NativeSignalEvent>() == 64);
    assert!(std::mem::align_of::<NativeSignalEvent>() == 8);
    assert!(std::mem::offset_of!(NativeSignalEvent, signal_number) == 8);
    assert!(std::mem::offset_of!(NativeSignalEvent, notification) == 12);
    assert!(std::mem::offset_of!(NativeSignalEvent, reserved) == 16);
};

/// Owns one timer in this process. POSIX timers are not inherited by a child
/// created with fork. Dropping an owner attempts deletion once.
#[derive(Debug)]
#[must_use = "dropping the timer deletes the owned native timer"]
pub struct PosixTimer(i32);

impl Drop for PosixTimer {
    fn drop(&mut self) {
        let _ = delete_id(self.0);
    }
}

/// Creates one owned timer with explicit SIGEV_NONE. Expiration never requests
/// signal delivery or a callback. The kernel validates the selected clock.
pub fn timer_create(clock: i32) -> Result<PosixTimer, SyscallError> {
    let notification = NativeSignalEvent::none();
    let mut timer_id = -1_i32;
    let raw = unsafe {
        abi::call(
            TIMER_CREATE,
            [
                clock as usize,
                ptr::from_ref(&notification) as usize,
                ptr::from_mut(&mut timer_id) as usize,
                0,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)?;
    if timer_id < 0 {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    Ok(PosixTimer(timer_id))
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(i32)]
pub enum TimerMode {
    Relative = 0,
    Absolute = 1,
}

/// Updates the timer, returning its previous interval and remaining time. An
/// initial value of zero disarms the timer regardless of mode.
pub fn timer_settime(
    timer: &PosixTimer,
    mode: TimerMode,
    new: TimerSpec,
) -> Result<TimerSpec, SyscallError> {
    let mut previous = TimerSpec::default();
    let raw = unsafe {
        abi::call(
            TIMER_SETTIME,
            [
                timer.0 as usize,
                mode as usize,
                ptr::from_ref(&new) as usize,
                ptr::from_mut(&mut previous) as usize,
                0,
                0,
            ],
        )
    };
    checked_settings(raw, previous)
}

/// Returns the interval and remaining time reported by Linux. For SIGEV_NONE
/// on kernels that retain an old expiry after disarming, the remaining time
/// can stay positive until that expiry passes. The interval is zero.
pub fn timer_gettime(timer: &PosixTimer) -> Result<TimerSpec, SyscallError> {
    let mut settings = TimerSpec::default();
    let raw = unsafe {
        abi::call(
            TIMER_GETTIME,
            [
                timer.0 as usize,
                ptr::from_mut(&mut settings) as usize,
                0,
                0,
                0,
                0,
            ],
        )
    };
    checked_settings(raw, settings)
}

fn checked_settings(raw: isize, settings: TimerSpec) -> Result<TimerSpec, SyscallError> {
    decode_zero(raw)?;
    if settings.initial.seconds() < 0 || settings.interval.seconds() < 0 {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    settings.checked(raw)
}

/// Returns the kernel's last notification overrun count. In SIGEV_NONE mode
/// the kernel does not deliver notifications, so this count remains zero.
pub fn timer_getoverrun(timer: &PosixTimer) -> Result<u32, SyscallError> {
    let raw = unsafe { abi::call(TIMER_GETOVERRUN, [timer.0 as usize, 0, 0, 0, 0, 0]) };
    let count = decode_nonnegative(raw)?;
    i32::try_from(count)
        .map(|value| value as u32)
        .map_err(|_| SyscallError::UnexpectedReturn(raw))
}

#[derive(Debug)]
pub struct TimerDeleteError {
    error: SyscallError,
    timer: PosixTimer,
}

impl TimerDeleteError {
    pub fn into_parts(self) -> (SyscallError, PosixTimer) {
        (self.error, self.timer)
    }
}

impl fmt::Display for TimerDeleteError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "timer_delete: {}", self.error)
    }
}

impl std::error::Error for TimerDeleteError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        Some(&self.error)
    }
}

/// Deletes the timer and consumes its owner. If the deletion fails the error
/// retains the owner so the caller can decide when to retry cleanup.
pub fn timer_delete(timer: PosixTimer) -> Result<(), TimerDeleteError> {
    match delete_id(timer.0) {
        Ok(()) => {
            std::mem::forget(timer);
            Ok(())
        }
        Err(error) => Err(TimerDeleteError { error, timer }),
    }
}

fn delete_id(timer_id: i32) -> Result<(), SyscallError> {
    decode_zero(unsafe { abi::call(TIMER_DELETE, [timer_id as usize, 0, 0, 0, 0, 0]) })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{CLOCK_MONOTONIC, EINVAL};

    #[test]
    fn posix_timer_delete_consumes_ownership_and_drop_cleans_up() {
        let explicit = timer_create(CLOCK_MONOTONIC).unwrap();
        let id = explicit.0;
        timer_delete(explicit).unwrap();
        assert!(delete_id(id).unwrap_err().is_errno(EINVAL));

        let implicit = timer_create(CLOCK_MONOTONIC).unwrap();
        let id = implicit.0;
        drop(implicit);
        assert!(delete_id(id).unwrap_err().is_errno(EINVAL));
    }
}
