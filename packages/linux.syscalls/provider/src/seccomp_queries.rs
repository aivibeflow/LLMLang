use super::{abi, decode_zero, SyscallError};
use std::mem::{align_of, offset_of, size_of};

const SECCOMP: usize = 317;
const SECCOMP_GET_ACTION_AVAIL: usize = 2;
const SECCOMP_GET_NOTIF_SIZES: usize = 3;

/// The action words defined by the pinned seccomp UAPI. The query supplies
/// only the action word, without any filter program or action data.
#[repr(u32)]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SeccompAction {
    KillProcess = 0x8000_0000,
    KillThread = 0x0000_0000,
    Trap = 0x0003_0000,
    Errno = 0x0005_0000,
    UserNotify = 0x7fc0_0000,
    Trace = 0x7ff0_0000,
    Log = 0x7ffc_0000,
    Allow = 0x7fff_0000,
}

#[repr(C)]
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct SeccompNotifSizes {
    pub notification: u16,
    pub response: u16,
    pub data: u16,
}

const _: () = {
    assert!(size_of::<SeccompAction>() == 4);
    assert!(size_of::<SeccompNotifSizes>() == 6);
    assert!(align_of::<SeccompNotifSizes>() == 2);
    assert!(offset_of!(SeccompNotifSizes, response) == 2);
    assert!(offset_of!(SeccompNotifSizes, data) == 4);
};

/// Checks whether the kernel supports a seccomp action. Linux supplies
/// EOPNOTSUPP when the action is unavailable. This query installs nothing.
pub fn seccomp_get_action_avail(action: SeccompAction) -> Result<(), SyscallError> {
    let native = action as u32;
    decode_zero(unsafe {
        abi::call(
            SECCOMP,
            [
                SECCOMP_GET_ACTION_AVAIL,
                0,
                (&native as *const u32) as usize,
                0,
                0,
                0,
            ],
        )
    })
}

/// Reports the notification, response and seccomp data sizes advertised by
/// the kernel. This query does not create a listener or install a filter.
pub fn seccomp_get_notif_sizes() -> Result<SeccompNotifSizes, SyscallError> {
    let mut sizes = SeccompNotifSizes::default();
    let raw = unsafe {
        abi::call(
            SECCOMP,
            [
                SECCOMP_GET_NOTIF_SIZES,
                0,
                (&mut sizes as *mut SeccompNotifSizes) as usize,
                0,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)?;
    if sizes.notification == 0 || sizes.response == 0 || sizes.data == 0 {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    Ok(sizes)
}
