//! Native process accounting, reboot policy, and staged kernel image removal.
use std::ffi::CStr;

use crate::{abi, decode_zero, SyscallError};

const ACCT: usize = 163;
const REBOOT: usize = 169;
const KEXEC_LOAD: usize = 246;
const KEXEC_FILE_LOAD: usize = 320;
const KEXEC_FILE_UNLOAD: usize = 1;
const REBOOT_MAGIC1: usize = 0xfee1_dead;
const REBOOT_MAGIC2: usize = 0x2812_1969;
const REBOOT_CAD_OFF: usize = 0;
const REBOOT_CAD_ON: usize = 0x89ab_cdef;

/// Enable process accounting to the existing path or disable it with a null
/// path. Linux authorizes the operation with CAP_SYS_PACCT.
pub fn acct(path: Option<&CStr>) -> Result<(), SyscallError> {
    let path = path.map_or(0, |string| string.as_ptr() as usize);
    decode_zero(unsafe { abi::call(ACCT, [path, 0, 0, 0, 0, 0]) })
}

/// Select the kernel Ctrl-Alt-Delete policy. This invokes one of the two
/// returning policy commands of reboot, with a null optional argument.
pub fn reboot_cad_control(enabled: bool) -> Result<(), SyscallError> {
    let mode = if enabled {
        REBOOT_CAD_ON
    } else {
        REBOOT_CAD_OFF
    };
    decode_zero(unsafe { abi::call(REBOOT, [REBOOT_MAGIC1, REBOOT_MAGIC2, mode, 0, 0, 0]) })
}

/// Remove any staged normal (non-crash) image through the segment-based ABI.
/// No buffers or image are supplied, and the running kernel is unaffected.
pub fn kexec_load_unload() -> Result<(), SyscallError> {
    decode_zero(unsafe { abi::call(KEXEC_LOAD, [0; 6]) })
}

/// Remove any staged normal (non-crash) image through the descriptor-based
/// ABI. The unload selector requires no live input descriptors or buffers.
pub fn kexec_file_unload() -> Result<(), SyscallError> {
    decode_zero(unsafe {
        abi::call(
            KEXEC_FILE_LOAD,
            [usize::MAX, usize::MAX, 0, 0, KEXEC_FILE_UNLOAD, 0],
        )
    })
}
