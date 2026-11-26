use super::{abi, decode_nonnegative, decode_zero, SyscallError, Timespec};

const SCHED_YIELD: usize = 24;
const PERSONALITY: usize = 135;
const SCHED_GET_PRIORITY_MAX: usize = 146;
const SCHED_GET_PRIORITY_MIN: usize = 147;
const SCHED_RR_GET_INTERVAL: usize = 148;
const GETTID: usize = 186;
const GETCPU: usize = 309;
const MEMBARRIER: usize = 324;

/// Returns the calling thread's ID in the caller's PID namespace.
pub fn gettid() -> Result<i32, SyscallError> {
    let raw = unsafe { abi::invoke(GETTID, [0; 6]) };
    match decode_nonnegative(raw)? {
        id @ 1..=0x7fff_ffff => Ok(id as i32),
        _ => Err(SyscallError::UnexpectedReturn(raw)),
    }
}

/// Gives the scheduler one opportunity to run another eligible thread.
/// Linux can select the caller again immediately.
pub fn sched_yield() -> Result<(), SyscallError> {
    decode_zero(unsafe { abi::invoke(SCHED_YIELD, [0; 6]) })
}

pub fn sched_get_priority_min(policy: i32) -> Result<i32, SyscallError> {
    scheduler_bound(SCHED_GET_PRIORITY_MIN, policy)
}

pub fn sched_get_priority_max(policy: i32) -> Result<i32, SyscallError> {
    scheduler_bound(SCHED_GET_PRIORITY_MAX, policy)
}

fn scheduler_bound(operation: usize, policy: i32) -> Result<i32, SyscallError> {
    let raw = unsafe { abi::invoke(operation, [policy as usize, 0, 0, 0, 0, 0]) };
    match decode_nonnegative(raw)? {
        bound @ 0..=99 => Ok(bound as i32),
        _ => Err(SyscallError::UnexpectedReturn(raw)),
    }
}

/// Queries the scheduler quantum reported for a thread. Zero selects the
/// calling thread. The scheduler can report a zero duration.
pub fn sched_rr_get_interval(pid: i32) -> Result<Timespec, SyscallError> {
    let pid = usize::try_from(pid)
        .map_err(|_| SyscallError::InvalidInput("thread ID must be nonnegative"))?;
    let mut interval = Timespec::default();
    let output = (&mut interval as *mut Timespec) as usize;
    let raw = unsafe { abi::invoke(SCHED_RR_GET_INTERVAL, [pid, output, 0, 0, 0, 0]) };
    decode_zero(raw)?;
    if interval.seconds() < 0 {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    interval.checked(raw)
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CpuLocation {
    pub cpu: u32,
    pub node: u32,
}

/// Samples CPU and NUMA node together. The thread can migrate immediately
/// after the sample. The deprecated kernel cache argument is always null.
pub fn getcpu() -> Result<CpuLocation, SyscallError> {
    let mut cpu = u32::MAX;
    let mut node = u32::MAX;
    let raw = unsafe {
        abi::invoke(
            GETCPU,
            [
                (&mut cpu as *mut u32) as usize,
                (&mut node as *mut u32) as usize,
                0,
                0,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)?;
    if cpu == u32::MAX || node == u32::MAX {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    Ok(CpuLocation { cpu, node })
}

/// Reads the caller's personality and execution-domain flags using Linux's
/// fixed query sentinel. The caller cannot request an update.
pub fn personality_query() -> Result<u32, SyscallError> {
    let raw = unsafe { abi::invoke(PERSONALITY, [u32::MAX as usize, 0, 0, 0, 0, 0]) };
    u32::try_from(decode_nonnegative(raw)?).map_err(|_| SyscallError::UnexpectedReturn(raw))
}

/// Returns the Linux membarrier command-support mask. The query neither
/// registers a command nor requests a barrier.
pub fn membarrier_query() -> Result<u32, SyscallError> {
    let raw = unsafe { abi::invoke(MEMBARRIER, [0; 6]) };
    u32::try_from(decode_nonnegative(raw)?).map_err(|_| SyscallError::UnexpectedReturn(raw))
}
