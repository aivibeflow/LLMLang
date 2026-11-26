//! Native signal delivery scoped to an owned child or the current thread.
use super::{
    abi, decode_zero, getpid, gettid, ChildPid, ChildSignal, CurrentThreadSignalScope,
    SyscallError, UserSignal,
};

const KILL: usize = 62;
const TKILL: usize = 200;
pub(super) const TGKILL: usize = 234;

/// Checks or sends TERM using the owned child's numeric PID. The caller must
/// exclude independent and automatic reaping so the PID cannot be reused.
/// Signal success is separate from collecting the child's resulting status.
pub fn kill(child: &ChildPid, signal: ChildSignal) -> Result<(), SyscallError> {
    let pid = child
        .pid()
        .ok_or(SyscallError::InvalidInput("child has already been reaped"))?;
    decode_zero(unsafe { abi::invoke(KILL, [pid as usize, signal as usize, 0, 0, 0, 0]) })
}

fn check_selected(
    scope: &CurrentThreadSignalScope,
    signal: UserSignal,
) -> Result<(), SyscallError> {
    if !scope.permits(signal) {
        return Err(SyscallError::InvalidInput(
            "signal is outside the current thread mask scope",
        ));
    }
    Ok(())
}

/// Sends a selected blocked user signal to the calling thread using tkill.
/// Consume pending signals before leaving the mask scope.
pub fn tkill(scope: &CurrentThreadSignalScope, signal: UserSignal) -> Result<(), SyscallError> {
    check_selected(scope, signal)?;
    let thread = gettid()? as usize;
    decode_zero(unsafe { abi::invoke(TKILL, [thread, signal as usize, 0, 0, 0, 0]) })
}

/// Sends a selected blocked user signal to the calling thread, qualifying
/// the target by its process ID. Consume pending signals before leaving scope.
pub fn tgkill(scope: &CurrentThreadSignalScope, signal: UserSignal) -> Result<(), SyscallError> {
    check_selected(scope, signal)?;
    let process = getpid()? as usize;
    let thread = gettid()? as usize;
    decode_zero(unsafe { abi::invoke(TGKILL, [process, thread, signal as usize, 0, 0, 0]) })
}
