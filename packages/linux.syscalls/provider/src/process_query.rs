use super::{abi, decode_nonnegative, decode_zero, SyscallError};

const GETRLIMIT: usize = 97;
const GETRUSAGE: usize = 98;
const GETPGID: usize = 121;
const GETSID: usize = 124;
const GETPRIORITY: usize = 140;
const SCHED_GETPARAM: usize = 143;
const SCHED_GETSCHEDULER: usize = 145;
const PRLIMIT64: usize = 302;
const SCHED_RESET_ON_FORK: i32 = 0x4000_0000;

/// Linux resource-limit selectors for the pinned x86-64 ABI.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum LimitResource {
    Cpu = 0,
    FileSize = 1,
    Data = 2,
    Stack = 3,
    Core = 4,
    ResidentSet = 5,
    Processes = 6,
    OpenFiles = 7,
    LockedMemory = 8,
    AddressSpace = 9,
    Locks = 10,
    PendingSignals = 11,
    MessageQueue = 12,
    Nice = 13,
    RealtimePriority = 14,
    RealtimeTime = 15,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Limit {
    Finite(u64),
    Unlimited,
}

impl Limit {
    fn from_native(value: u64) -> Self {
        match value {
            u64::MAX => Self::Unlimited,
            finite => Self::Finite(finite),
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Rlimit {
    pub soft: Limit,
    pub hard: Limit,
}

#[derive(Default)]
#[repr(C)]
struct NativeRlimit {
    soft: u64,
    hard: u64,
}

impl From<NativeRlimit> for Rlimit {
    fn from(value: NativeRlimit) -> Self {
        Self {
            soft: Limit::from_native(value.soft),
            hard: Limit::from_native(value.hard),
        }
    }
}

/// Queries a resource limit for the current process.
pub fn getrlimit(resource: LimitResource) -> Result<Rlimit, SyscallError> {
    let mut limits = NativeRlimit::default();
    let output = (&mut limits as *mut NativeRlimit) as usize;
    decode_zero(unsafe { abi::invoke(GETRLIMIT, [resource as usize, output, 0, 0, 0, 0]) })?;
    Ok(limits.into())
}

/// Queries the current process through prlimit64, with no replacement limit.
pub fn prlimit64(resource: LimitResource) -> Result<Rlimit, SyscallError> {
    let mut limits = NativeRlimit::default();
    let output = (&mut limits as *mut NativeRlimit) as usize;
    decode_zero(unsafe { abi::invoke(PRLIMIT64, [0, resource as usize, 0, output, 0, 0]) })?;
    Ok(limits.into())
}

fn pid_argument(pid: i32) -> Result<usize, SyscallError> {
    usize::try_from(pid).map_err(|_| SyscallError::InvalidInput("process ID must be nonnegative"))
}

fn nonnegative_i32(raw: isize) -> Result<i32, SyscallError> {
    i32::try_from(decode_nonnegative(raw)?).map_err(|_| SyscallError::UnexpectedReturn(raw))
}

/// Queries the process group ID. PID zero selects the current process.
pub fn getpgid(pid: i32) -> Result<i32, SyscallError> {
    let pid = pid_argument(pid)?;
    nonnegative_i32(unsafe { abi::invoke(GETPGID, [pid, 0, 0, 0, 0, 0]) })
}

/// Queries the session ID. PID zero selects the current process.
pub fn getsid(pid: i32) -> Result<i32, SyscallError> {
    let pid = pid_argument(pid)?;
    nonnegative_i32(unsafe { abi::invoke(GETSID, [pid, 0, 0, 0, 0, 0]) })
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct SchedulePolicy {
    /// Kernel policy number, including any newly recognized policy numbers.
    pub code: i32,
    pub reset_on_fork: bool,
}

/// Queries the selected thread's scheduling policy and reset-on-fork flag.
/// PID zero selects the calling thread.
pub fn sched_getscheduler(pid: i32) -> Result<SchedulePolicy, SyscallError> {
    let pid = pid_argument(pid)?;
    let value = nonnegative_i32(unsafe { abi::invoke(SCHED_GETSCHEDULER, [pid, 0, 0, 0, 0, 0]) })?;
    Ok(SchedulePolicy {
        code: value & !SCHED_RESET_ON_FORK,
        reset_on_fork: value & SCHED_RESET_ON_FORK != 0,
    })
}

#[derive(Default)]
#[repr(C)]
struct NativeSchedParam {
    sched_priority: i32,
}

/// Queries the selected thread's scheduling priority, from 0 to 99.
/// PID zero selects the calling thread.
pub fn sched_getparam(pid: i32) -> Result<i32, SyscallError> {
    let pid = pid_argument(pid)?;
    let mut parameter = NativeSchedParam::default();
    let output = (&mut parameter as *mut NativeSchedParam) as usize;
    decode_zero(unsafe { abi::invoke(SCHED_GETPARAM, [pid, output, 0, 0, 0, 0]) })?;
    match parameter.sched_priority {
        priority @ 0..=99 => Ok(priority),
        unexpected => Err(SyscallError::UnexpectedReturn(unexpected as isize)),
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum PriorityKind {
    Process = 0,
    ProcessGroup = 1,
    User = 2,
}

/// Queries niceness for the selected process, process group, or user. Zero
/// selects the current process, group, or real user ID, respectively.
pub fn getpriority(kind: PriorityKind, who: u32) -> Result<i32, SyscallError> {
    let raw = unsafe { abi::invoke(GETPRIORITY, [kind as usize, who as usize, 0, 0, 0, 0]) };
    decode_nice(raw)
}

fn decode_nice(raw: isize) -> Result<i32, SyscallError> {
    match decode_nonnegative(raw)? {
        biased @ 1..=40 => Ok(20 - biased as i32),
        _ => Err(SyscallError::UnexpectedReturn(raw)),
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum UsageScope {
    Children = -1,
    Process = 0,
    CallingThread = 1,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct UsageTime {
    pub seconds: u64,
    pub microseconds: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ResourceUsage {
    pub user: UsageTime,
    pub system: UsageTime,
    pub max_rss_kib: i64,
    pub integral_shared_memory: i64,
    pub integral_unshared_data: i64,
    pub integral_unshared_stack: i64,
    pub minor_faults: i64,
    pub major_faults: i64,
    pub swaps: i64,
    pub block_inputs: i64,
    pub block_outputs: i64,
    pub messages_sent: i64,
    pub messages_received: i64,
    pub signals_received: i64,
    pub voluntary_context_switches: i64,
    pub involuntary_context_switches: i64,
}

#[derive(Default)]
#[repr(C)]
struct NativeTimeval {
    seconds: i64,
    microseconds: i64,
}

impl TryFrom<NativeTimeval> for UsageTime {
    type Error = SyscallError;

    fn try_from(value: NativeTimeval) -> Result<Self, Self::Error> {
        let seconds = u64::try_from(value.seconds)
            .map_err(|_| SyscallError::UnexpectedReturn(value.seconds as isize))?;
        let microseconds = match value.microseconds {
            micros @ 0..=999_999 => micros as u32,
            unexpected => return Err(SyscallError::UnexpectedReturn(unexpected as isize)),
        };
        Ok(Self {
            seconds,
            microseconds,
        })
    }
}

#[derive(Default)]
#[repr(C)]
struct NativeRusage {
    user: NativeTimeval,
    system: NativeTimeval,
    max_rss: i64,
    ixrss: i64,
    idrss: i64,
    isrss: i64,
    minflt: i64,
    majflt: i64,
    nswap: i64,
    inblock: i64,
    oublock: i64,
    msgsnd: i64,
    msgrcv: i64,
    nsignals: i64,
    nvcsw: i64,
    nivcsw: i64,
}

const _: () = {
    assert!(std::mem::size_of::<NativeRlimit>() == 16);
    assert!(std::mem::offset_of!(NativeRlimit, hard) == 8);
    assert!(std::mem::size_of::<NativeSchedParam>() == 4);
    assert!(std::mem::size_of::<NativeTimeval>() == 16);
    assert!(std::mem::size_of::<NativeRusage>() == 144);
    assert!(std::mem::align_of::<NativeRusage>() == 8);
    assert!(std::mem::offset_of!(NativeRusage, system) == 16);
    assert!(std::mem::offset_of!(NativeRusage, max_rss) == 32);
    assert!(std::mem::offset_of!(NativeRusage, nivcsw) == 136);
};

/// Reads CPU times and resource counters for the selected scope. Linux may
/// return zero for historical counters that it does not maintain.
pub fn getrusage(who: UsageScope) -> Result<ResourceUsage, SyscallError> {
    let mut usage = NativeRusage::default();
    let output = (&mut usage as *mut NativeRusage) as usize;
    decode_zero(unsafe { abi::invoke(GETRUSAGE, [who as i32 as usize, output, 0, 0, 0, 0]) })?;
    Ok(ResourceUsage {
        user: usage.user.try_into()?,
        system: usage.system.try_into()?,
        max_rss_kib: usage.max_rss,
        integral_shared_memory: usage.ixrss,
        integral_unshared_data: usage.idrss,
        integral_unshared_stack: usage.isrss,
        minor_faults: usage.minflt,
        major_faults: usage.majflt,
        swaps: usage.nswap,
        block_inputs: usage.inblock,
        block_outputs: usage.oublock,
        messages_sent: usage.msgsnd,
        messages_received: usage.msgrcv,
        signals_received: usage.nsignals,
        voluntary_context_switches: usage.nvcsw,
        involuntary_context_switches: usage.nivcsw,
    })
}

#[cfg(test)]
mod tests {
    use super::decode_nice;
    use crate::SyscallError;

    #[test]
    fn priority_decoder_separates_negative_nice_from_errno() {
        assert_eq!(decode_nice(40), Ok(-20));
        assert_eq!(decode_nice(21), Ok(-1));
        assert_eq!(decode_nice(20), Ok(0));
        assert_eq!(decode_nice(1), Ok(19));
        assert!(decode_nice(-1).unwrap_err().is_errno(1));
        assert_eq!(decode_nice(0), Err(SyscallError::UnexpectedReturn(0)));
        assert_eq!(decode_nice(41), Err(SyscallError::UnexpectedReturn(41)));
    }
}
