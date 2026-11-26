//! The native x86-64 legacy filesystem status observation.
use std::mem::{align_of, offset_of, size_of};
use std::os::fd::BorrowedFd;

use crate::{abi, decode_zero, fstat, SyscallError};

const USTAT: usize = 136;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct LegacyUstat {
    /// Signed legacy field, which can truncate a filesystem's free-block count.
    pub free_blocks: i32,
    pub free_inodes: u64,
    pub filesystem_name: [u8; 6],
    pub filesystem_pack: [u8; 6],
}

#[derive(Default)]
#[repr(C)]
struct NativeUstat {
    free_blocks: i32,
    block_padding: [u8; 4],
    free_inodes: u64,
    filesystem_name: [u8; 6],
    filesystem_pack: [u8; 6],
    tail_padding: [u8; 4],
}

const _: () = {
    assert!(size_of::<NativeUstat>() == 32);
    assert!(align_of::<NativeUstat>() == 8);
    assert!(offset_of!(NativeUstat, free_inodes) == 8);
    assert!(offset_of!(NativeUstat, filesystem_name) == 16);
    assert!(offset_of!(NativeUstat, filesystem_pack) == 22);
};

/// Query the filesystem selected by the live descriptor. Native fstat's
/// device number is already in the encoding consumed by Linux ustat.
pub fn ustat(file: BorrowedFd<'_>) -> Result<LegacyUstat, SyscallError> {
    let device = u32::try_from(fstat(file)?.device)
        .map_err(|_| SyscallError::InvalidInput("device number exceeds the native ustat field"))?;
    let mut output = NativeUstat::default();
    let raw = unsafe {
        abi::call(
            USTAT,
            [
                device as usize,
                std::ptr::from_mut(&mut output) as usize,
                0,
                0,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)?;
    Ok(LegacyUstat {
        free_blocks: output.free_blocks,
        free_inodes: output.free_inodes,
        filesystem_name: output.filesystem_name,
        filesystem_pack: output.filesystem_pack,
    })
}
