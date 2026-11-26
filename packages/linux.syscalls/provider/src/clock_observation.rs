//! Linux x86-64 time discipline queries with the adjustment modes fixed at zero.

use super::{abi, decode_nonnegative, SyscallError, CLOCK_REALTIME};

const ADJTIMEX: usize = 159;
const CLOCK_ADJTIME: usize = 305;
const STA_NANO: i32 = 0x2000;

#[repr(C)]
#[derive(Default)]
struct NativeTimex {
    modes: u32,
    pad_modes: u32,
    offset: i64,
    frequency: i64,
    maximum_error: i64,
    estimated_error: i64,
    status: i32,
    pad_status: u32,
    constant: i64,
    precision: i64,
    tolerance: i64,
    time_seconds: i64,
    time_fraction: i64,
    tick: i64,
    pps_frequency: i64,
    jitter: i64,
    shift: i32,
    pad_shift: u32,
    stability: i64,
    jitter_count: i64,
    calibration_count: i64,
    error_count: i64,
    stability_count: i64,
    tai: i32,
    reserved: [u32; 11],
}

const _: () = {
    use std::mem::{align_of, offset_of, size_of};

    assert!(size_of::<NativeTimex>() == 208);
    assert!(align_of::<NativeTimex>() == 8);
    assert!(offset_of!(NativeTimex, modes) == 0);
    assert!(offset_of!(NativeTimex, offset) == 8);
    assert!(offset_of!(NativeTimex, frequency) == 16);
    assert!(offset_of!(NativeTimex, maximum_error) == 24);
    assert!(offset_of!(NativeTimex, estimated_error) == 32);
    assert!(offset_of!(NativeTimex, status) == 40);
    assert!(offset_of!(NativeTimex, constant) == 48);
    assert!(offset_of!(NativeTimex, precision) == 56);
    assert!(offset_of!(NativeTimex, tolerance) == 64);
    assert!(offset_of!(NativeTimex, time_seconds) == 72);
    assert!(offset_of!(NativeTimex, time_fraction) == 80);
    assert!(offset_of!(NativeTimex, tick) == 88);
    assert!(offset_of!(NativeTimex, pps_frequency) == 96);
    assert!(offset_of!(NativeTimex, jitter) == 104);
    assert!(offset_of!(NativeTimex, shift) == 112);
    assert!(offset_of!(NativeTimex, stability) == 120);
    assert!(offset_of!(NativeTimex, jitter_count) == 128);
    assert!(offset_of!(NativeTimex, calibration_count) == 136);
    assert!(offset_of!(NativeTimex, error_count) == 144);
    assert!(offset_of!(NativeTimex, stability_count) == 152);
    assert!(offset_of!(NativeTimex, tai) == 160);
    assert!(offset_of!(NativeTimex, reserved) == 164);
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ClockDisciplineState {
    Synchronized,
    InsertLeap,
    DeleteLeap,
    LeapInProgress,
    LeapOccurred,
    /// Linux TIME_ERROR, a successful observation of a clock discipline error.
    Error,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum TimexSubseconds {
    Microseconds(u32),
    Nanoseconds(u32),
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct TimexObservation {
    pub state: ClockDisciplineState,
    /// The unit follows the clock resolution in time_fraction.
    pub offset: i64,
    /// Native scaled parts per million (2^16 units per ppm).
    pub frequency: i64,
    pub maximum_error: i64,
    pub estimated_error: i64,
    /// All native status bits, including bits this adapter does not name.
    pub status: i32,
    pub constant: i64,
    pub precision: i64,
    pub tolerance: i64,
    pub time_seconds: i64,
    pub time_fraction: TimexSubseconds,
    pub tick: i64,
    pub pps_frequency: i64,
    pub jitter: i64,
    pub shift: i32,
    pub stability: i64,
    pub jitter_count: i64,
    pub calibration_count: i64,
    pub error_count: i64,
    pub stability_count: i64,
    pub tai: i32,
}

fn decode_timex(raw: isize, native: NativeTimex) -> Result<TimexObservation, SyscallError> {
    let state = match decode_nonnegative(raw)? {
        0 => ClockDisciplineState::Synchronized,
        1 => ClockDisciplineState::InsertLeap,
        2 => ClockDisciplineState::DeleteLeap,
        3 => ClockDisciplineState::LeapInProgress,
        4 => ClockDisciplineState::LeapOccurred,
        5 => ClockDisciplineState::Error,
        _ => return Err(SyscallError::UnexpectedReturn(raw)),
    };
    let time_fraction = match native.status & STA_NANO {
        0 if (0..1_000_000).contains(&native.time_fraction) => {
            TimexSubseconds::Microseconds(native.time_fraction as u32)
        }
        STA_NANO if (0..1_000_000_000).contains(&native.time_fraction) => {
            TimexSubseconds::Nanoseconds(native.time_fraction as u32)
        }
        _ => return Err(SyscallError::UnexpectedReturn(raw)),
    };

    Ok(TimexObservation {
        state,
        offset: native.offset,
        frequency: native.frequency,
        maximum_error: native.maximum_error,
        estimated_error: native.estimated_error,
        status: native.status,
        constant: native.constant,
        precision: native.precision,
        tolerance: native.tolerance,
        time_seconds: native.time_seconds,
        time_fraction,
        tick: native.tick,
        pps_frequency: native.pps_frequency,
        jitter: native.jitter,
        shift: native.shift,
        stability: native.stability,
        jitter_count: native.jitter_count,
        calibration_count: native.calibration_count,
        error_count: native.error_count,
        stability_count: native.stability_count,
        tai: native.tai,
    })
}

/// Obtain the realtime clock discipline without requesting any adjustment.
pub fn adjtimex() -> Result<TimexObservation, SyscallError> {
    let mut native = NativeTimex::default();
    let raw = unsafe {
        abi::invoke(
            ADJTIMEX,
            [std::ptr::from_mut(&mut native) as usize, 0, 0, 0, 0, 0],
        )
    };
    decode_timex(raw, native)
}

/// Obtain the realtime clock discipline through clock_adjtime with modes zero.
pub fn clock_adjtime() -> Result<TimexObservation, SyscallError> {
    let mut native = NativeTimex::default();
    let raw = unsafe {
        abi::invoke(
            CLOCK_ADJTIME,
            [
                CLOCK_REALTIME as usize,
                std::ptr::from_mut(&mut native) as usize,
                0,
                0,
                0,
                0,
            ],
        )
    };
    decode_timex(raw, native)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn decode_timex_distinguishes_clock_error_from_errno_and_checks_resolution() {
        let states = [
            ClockDisciplineState::Synchronized,
            ClockDisciplineState::InsertLeap,
            ClockDisciplineState::DeleteLeap,
            ClockDisciplineState::LeapInProgress,
            ClockDisciplineState::LeapOccurred,
            ClockDisciplineState::Error,
        ];
        for (raw, state) in states.into_iter().enumerate() {
            let observed = decode_timex(raw as isize, NativeTimex::default()).unwrap();
            assert_eq!(observed.state, state);
        }
        assert!(decode_timex(-1, NativeTimex::default())
            .unwrap_err()
            .is_errno(1));
        assert_eq!(
            decode_timex(6, NativeTimex::default()),
            Err(SyscallError::UnexpectedReturn(6)),
        );

        let reported = NativeTimex {
            status: STA_NANO | 0x40,
            time_fraction: 999_999_999,
            ..NativeTimex::default()
        };
        let observed = decode_timex(5, reported).unwrap();
        assert_eq!(observed.status, STA_NANO | 0x40);
        assert_eq!(
            observed.time_fraction,
            TimexSubseconds::Nanoseconds(999_999_999)
        );
        for (status, time_fraction) in [(0, -1), (0, 1_000_000), (STA_NANO, 1_000_000_000)] {
            assert_eq!(
                decode_timex(
                    0,
                    NativeTimex {
                        status,
                        time_fraction,
                        ..NativeTimex::default()
                    }
                ),
                Err(SyscallError::UnexpectedReturn(0)),
            );
        }
    }
}
