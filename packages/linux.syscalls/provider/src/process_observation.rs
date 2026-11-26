//! Program-break observation and terminal events for an owned direct child.
use crate::{abi, decode_nonnegative, decode_zero, ChildPid, SyscallError};

const BRK: usize = 12;
const WAITID: usize = 247;
const P_PID: usize = 1;
const WEXITED: usize = 4;
const SIGCHLD: i32 = 17;

pub fn brk_query() -> Result<usize, SyscallError> {
    let raw = unsafe { abi::call(BRK, [0; 6]) };
    match decode_nonnegative(raw)? {
        0 => Err(SyscallError::UnexpectedReturn(raw)),
        current => Ok(current),
    }
}

#[repr(C)]
struct WaitSiginfo {
    signo: i32,
    errno: i32,
    code: i32,
    header_padding: i32,
    pid: i32,
    uid: u32,
    status: i32,
    padding: i32,
    user_time: i64,
    system_time: i64,
    reserved: [u8; 80],
}

const _: () = {
    assert!(std::mem::size_of::<WaitSiginfo>() == 128);
    assert!(std::mem::align_of::<WaitSiginfo>() == 8);
    assert!(std::mem::offset_of!(WaitSiginfo, pid) == 16);
    assert!(std::mem::offset_of!(WaitSiginfo, status) == 24);
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum WaitIdOutcome {
    Exited(u8),
    Signaled { signal: u8, core_dumped: bool },
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct WaitIdStatus {
    pub pid: i32,
    pub uid: u32,
    pub outcome: WaitIdOutcome,
}

pub fn waitid(child: &mut ChildPid, nohang: bool) -> Result<Option<WaitIdStatus>, SyscallError> {
    let pid = child.pid().ok_or(SyscallError::InvalidInput(
        "child has already been collected",
    ))?;
    let mut info = WaitSiginfo {
        signo: 0,
        errno: 0,
        code: 0,
        header_padding: 0,
        pid: 0,
        uid: 0,
        status: 0,
        padding: 0,
        user_time: 0,
        system_time: 0,
        reserved: [0; 80],
    };
    let flags = WEXITED | usize::from(nohang) * crate::WNOHANG as usize;
    let raw = unsafe {
        abi::call(
            WAITID,
            [
                P_PID,
                pid as usize,
                std::ptr::from_mut(&mut info) as usize,
                flags,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)?;
    if info.pid == 0 && nohang {
        return Ok(None);
    }
    // A WEXITED observation reaps this child even if decoding later fails.
    child.retire();
    if info.pid != pid || info.signo != SIGCHLD || info.errno != 0 {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    let status = u8::try_from(info.status).map_err(|_| SyscallError::UnexpectedReturn(raw))?;
    let outcome = match info.code {
        1 => WaitIdOutcome::Exited(status),
        2 | 3 if (1..=64).contains(&status) => WaitIdOutcome::Signaled {
            signal: status,
            core_dumped: info.code == 3,
        },
        _ => return Err(SyscallError::UnexpectedReturn(raw)),
    };
    Ok(Some(WaitIdStatus {
        pid,
        uid: info.uid,
        outcome,
    }))
}
