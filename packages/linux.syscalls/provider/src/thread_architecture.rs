//! Read-only x86-64 segment queries and operations that remove I/O privileges.

use super::{abi, decode_nonnegative, decode_zero, SyscallError};
use std::ptr;

const MODIFY_LDT: usize = 154;
const ARCH_PRCTL: usize = 158;
const IOPL: usize = 172;
const IOPERM: usize = 173;

const ARCH_GET_FS: usize = 0x1003;
const ARCH_GET_GS: usize = 0x1004;
const LDT_BYTES_MAX: usize = 8192 * 8;
const IO_PORT_COUNT: u32 = 65_536;

fn get_segment_base(command: usize) -> Result<u64, SyscallError> {
    let mut output = 0_u64;
    let raw = unsafe {
        abi::invoke(
            ARCH_PRCTL,
            [command, ptr::from_mut(&mut output) as usize, 0, 0, 0, 0],
        )
    };
    decode_zero(raw)?;
    Ok(output)
}

/// Observe the calling thread's FS base as a number.
pub fn arch_prctl_get_fs() -> Result<u64, SyscallError> {
    get_segment_base(ARCH_GET_FS)
}

/// Observe the calling thread's GS base as a number.
pub fn arch_prctl_get_gs() -> Result<u64, SyscallError> {
    get_segment_base(ARCH_GET_GS)
}

fn ldt_byte_count(raw: isize, capacity: usize) -> Result<usize, SyscallError> {
    // Native modify_ldt returns a zero-extended signed 32-bit result. An
    // error from syscall dispatch may already have been sign-extended.
    let signed = u32::try_from(raw).map_or(raw, |value| value as i32 as isize);
    if !(-4095..=capacity as isize).contains(&signed) {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    decode_nonnegative(signed)
}

/// Read up to buffer.len() bytes of the calling address space's LDT.
/// A missing LDT returns zero and leaves the buffer untouched.
pub fn modify_ldt_read(buffer: &mut [u8]) -> Result<usize, SyscallError> {
    if buffer.len() > LDT_BYTES_MAX {
        return Err(SyscallError::InvalidInput(
            "LDT read capacity exceeds 65536 bytes",
        ));
    }
    let raw = unsafe {
        abi::invoke(
            MODIFY_LDT,
            [0, buffer.as_mut_ptr() as usize, buffer.len(), 0, 0, 0],
        )
    };
    ldt_byte_count(raw, buffer.len())
}

/// Lower the calling thread's emulated I/O privilege level to zero.
/// Port permissions granted independently through its I/O bitmap are unaffected.
pub fn iopl_drop() -> Result<(), SyscallError> {
    let raw = unsafe { abi::invoke(IOPL, [0; 6]) };
    decode_zero(raw)
}

fn check_port_range(first: u32, count: u32) -> Result<(), SyscallError> {
    if count == 0
        || first
            .checked_add(count)
            .is_none_or(|end| end > IO_PORT_COUNT)
    {
        return Err(SyscallError::InvalidInput(
            "invalid nonempty 16-bit I/O port range",
        ));
    }
    Ok(())
}

/// Revoke bitmap permissions for [first, first + count) in the calling thread.
/// This operation does not change its emulated I/O privilege level.
pub fn ioperm_revoke(first: u32, count: u32) -> Result<(), SyscallError> {
    check_port_range(first, count)?;
    let raw = unsafe { abi::invoke(IOPERM, [first as usize, count as usize, 0, 0, 0, 0]) };
    decode_zero(raw)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ldt_decode_handles_both_errno_forms_and_bounds() {
        assert!(ldt_byte_count((-14_i32) as u32 as isize, 8)
            .unwrap_err()
            .is_errno(14));
        assert!(ldt_byte_count(-1, 8).unwrap_err().is_errno(1));
        assert_eq!(ldt_byte_count(0, 8), Ok(0));
        assert_eq!(ldt_byte_count(8, 8), Ok(8));
        assert_eq!(ldt_byte_count(9, 8), Err(SyscallError::UnexpectedReturn(9)));
        assert_eq!(
            ldt_byte_count(-4096, 8),
            Err(SyscallError::UnexpectedReturn(-4096))
        );
    }

    #[test]
    fn architecture_query_and_revoke_bounds_are_checked_before_syscall() {
        assert!(matches!(
            modify_ldt_read(&mut vec![0; LDT_BYTES_MAX + 1]),
            Err(SyscallError::InvalidInput(_))
        ));
        assert!(check_port_range(0, 65_536).is_ok());
        assert!(check_port_range(65_535, 1).is_ok());
        for (first, count) in [(0, 0), (65_536, 1), (65_535, 2), (u32::MAX, 2)] {
            assert!(matches!(
                ioperm_revoke(first, count),
                Err(SyscallError::InvalidInput(_))
            ));
        }
    }
}
