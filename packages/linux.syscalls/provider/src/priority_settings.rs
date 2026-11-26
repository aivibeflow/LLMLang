//! Current-thread scheduling priorities.
use crate::{abi, decode_nonnegative, decode_zero, SyscallError};

const SETPRIORITY: usize = 141;
const IOPRIO_SET: usize = 251;
const IOPRIO_GET: usize = 252;
const PROCESS: usize = 1;
const IOPRIO_CLASS_SHIFT: usize = 13;
const IOPRIO_DATA_MASK: u16 = (1 << IOPRIO_CLASS_SHIFT) - 1;

/// Request a nonnegative nice value for the calling thread.
pub fn setpriority_current(nice: i32) -> Result<(), SyscallError> {
    if !(0..=19).contains(&nice) {
        return Err(SyscallError::InvalidInput("nice must be 0 through 19"));
    }
    // PRIO_PROCESS is 0, distinct from IOPRIO_WHO_PROCESS.
    decode_zero(unsafe { abi::call(SETPRIORITY, [0, 0, nice as usize, 0, 0, 0]) })
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum IoPriority {
    Normal,
    BestEffort(u8),
    Idle,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct IoPriorityObservation {
    pub class: u16,
    /// Native class data, including bits outside the best-effort priority.
    pub data: u16,
}

pub fn ioprio_get_current() -> Result<IoPriorityObservation, SyscallError> {
    let raw = unsafe { abi::call(IOPRIO_GET, [PROCESS, 0, 0, 0, 0, 0]) };
    let value =
        u16::try_from(decode_nonnegative(raw)?).map_err(|_| SyscallError::UnexpectedReturn(raw))?;
    Ok(IoPriorityObservation {
        class: value >> IOPRIO_CLASS_SHIFT,
        data: value & IOPRIO_DATA_MASK,
    })
}

/// Set an ordinary I/O priority for the calling thread.
pub fn ioprio_set_current(priority: IoPriority) -> Result<(), SyscallError> {
    let (class, data) = match priority {
        IoPriority::Normal => (0, 0),
        IoPriority::BestEffort(level @ 0..=7) => (2, usize::from(level)),
        IoPriority::BestEffort(_) => {
            return Err(SyscallError::InvalidInput(
                "best-effort priority must be 0 through 7",
            ));
        }
        IoPriority::Idle => (3, 0),
    };
    let value = (class << IOPRIO_CLASS_SHIFT) | data;
    decode_zero(unsafe { abi::call(IOPRIO_SET, [PROCESS, 0, value, 0, 0, 0]) })
}
