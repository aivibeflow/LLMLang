//! Native realtime clock updates. The caller needs permission to set the clock.

use super::{abi, decode_zero, SyscallError, Timespec, Timeval, CLOCK_REALTIME};
use std::mem::{align_of, size_of};
use std::ptr;

const CLOCK_SETTIME: usize = 227;
const SETTIMEOFDAY: usize = 164;

const _: () = {
    assert!(size_of::<Timespec>() == 16 && align_of::<Timespec>() == 8);
    assert!(size_of::<Timeval>() == 16 && align_of::<Timeval>() == 8);
};

/// Set CLOCK_REALTIME from a normalized seconds and nanoseconds timestamp.
/// Linux checks the epoch range and the caller's authority to change the clock.
pub fn clock_settime(value: Timespec) -> Result<(), SyscallError> {
    let raw = unsafe {
        abi::invoke(
            CLOCK_SETTIME,
            [
                CLOCK_REALTIME as usize,
                ptr::from_ref(&value) as usize,
                0,
                0,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)
}

/// Set the realtime clock from a normalized seconds and microseconds timestamp.
/// The obsolete timezone pointer is always null.
pub fn settimeofday(value: Timeval) -> Result<(), SyscallError> {
    let raw = unsafe {
        abi::invoke(
            SETTIMEOFDAY,
            [ptr::from_ref(&value) as usize, 0, 0, 0, 0, 0],
        )
    };
    decode_zero(raw)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn native_clock_inputs_enforce_fraction_widths_without_setting_time() {
        let nanos = Timespec::new(-1, 999_999_999).unwrap();
        assert_eq!((nanos.seconds(), nanos.nanos()), (-1, 999_999_999));
        let micros = Timeval::new(-1, 999_999).unwrap();
        assert_eq!((micros.seconds(), micros.micros()), (-1, 999_999));
        assert!(Timespec::new(0, -1).is_err());
        assert!(Timespec::new(0, 1_000_000_000).is_err());
        assert!(Timeval::new(0, -1).is_err());
        assert!(Timeval::new(0, 1_000_000).is_err());
    }
}
