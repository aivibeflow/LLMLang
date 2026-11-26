//! Selected current-thread observations from the native signal queue.
use std::mem::{align_of, offset_of, size_of};

use crate::{
    abi, decode_nonnegative, CurrentThreadSignalScope, SyscallError, Timespec, UserSignal,
};

const RT_SIGTIMEDWAIT: usize = 128;
const SI_USER: i32 = 0;
const SI_TKILL: i32 = -6;
const SI_QUEUE: i32 = -1;

#[repr(C)]
pub(super) struct NativeSignalInfo {
    number: i32,
    errno: i32,
    code: i32,
    padding: u32,
    pid: i32,
    uid: u32,
    value: u64,
    remainder: [u8; 96],
}

const _: () = {
    assert!(size_of::<NativeSignalInfo>() == 128);
    assert!(align_of::<NativeSignalInfo>() == 8);
    assert!(offset_of!(NativeSignalInfo, pid) == 16);
    assert!(offset_of!(NativeSignalInfo, uid) == 20);
    assert!(offset_of!(NativeSignalInfo, value) == 24);
};

impl NativeSignalInfo {
    pub(super) const fn empty() -> Self {
        Self {
            number: 0,
            errno: 0,
            code: 0,
            padding: 0,
            pid: 0,
            uid: 0,
            value: 0,
            remainder: [0; 96],
        }
    }

    // The caller supplies observed credentials from this isolated process.
    pub(super) fn self_queue(signal: UserSignal, pid: i32, uid: u32, value: i32) -> Self {
        Self {
            number: signal as i32,
            code: SI_QUEUE,
            pid,
            uid,
            value: u64::from(value as u32),
            ..Self::empty()
        }
    }

    pub(super) fn matches_queue(&self, signal: UserSignal, pid: i32, uid: u32, value: i32) -> bool {
        self.number == signal as i32
            && self.code == SI_QUEUE
            && self.errno == 0
            && self.pid == pid
            && self.uid == uid
            && self.value == u64::from(value as u32)
    }
}

pub(super) fn raw_signal_wait(
    mask: &u64,
    info: &mut NativeSignalInfo,
    timeout: Option<&Timespec>,
) -> isize {
    let timeout = timeout.map_or(0, |value| std::ptr::from_ref(value) as usize);
    // The input mask, output record and optional timespec live through the call.
    unsafe {
        abi::invoke(
            RT_SIGTIMEDWAIT,
            [
                std::ptr::from_ref(mask) as usize,
                std::ptr::from_mut(info) as usize,
                timeout,
                size_of::<u64>(),
                0,
                0,
            ],
        )
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct SignalWaitSender {
    pub pid: i32,
    pub uid: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct SignalWaitEvent {
    pub signal: UserSignal,
    pub code: i32,
    pub errno: i32,
    /// The reported sender for SI_USER, SI_TKILL and SI_QUEUE records.
    pub sender: Option<SignalWaitSender>,
    /// The native sival_int field for SI_QUEUE. The pointer view is outside
    /// this profile.
    pub queued_value: Option<i32>,
}

/// Consume a selected pending signal on the calling thread. The timeout is
/// relative, with None allowing an indefinite wait. The kernel returns EAGAIN
/// at the deadline (including an empty zero-timeout poll).
pub fn rt_sigtimedwait(
    scope: &CurrentThreadSignalScope,
    timeout: Option<Timespec>,
) -> Result<SignalWaitEvent, SyscallError> {
    if timeout.is_some_and(|value| value.seconds() < 0) {
        return Err(SyscallError::InvalidInput("negative signal wait timeout"));
    }
    let mut info = NativeSignalInfo::empty();
    let raw = raw_signal_wait(&scope.mask(), &mut info, timeout.as_ref());
    let observed = decode_nonnegative(raw)?;
    let signal = match observed {
        value if value == UserSignal::User1 as usize => UserSignal::User1,
        value if value == UserSignal::User2 as usize => UserSignal::User2,
        _ => return Err(SyscallError::UnexpectedReturn(raw)),
    };
    if info.number != signal as i32 || !scope.permits(signal) {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    Ok(SignalWaitEvent {
        signal,
        code: info.code,
        errno: info.errno,
        sender: matches!(info.code, SI_USER | SI_TKILL | SI_QUEUE).then_some(SignalWaitSender {
            pid: info.pid,
            uid: info.uid,
        }),
        queued_value: (info.code == SI_QUEUE).then_some(info.value as u32 as i32),
    })
}
