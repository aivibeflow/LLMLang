//! Ordinary scheduler updates for the current Linux thread.
use crate::{abi, decode_zero, SyscallError};

const SCHED_SETPARAM: usize = 142;
const SCHED_SETSCHEDULER: usize = 144;
const SCHED_SETATTR: usize = 314;

#[repr(u32)]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SchedulerPolicy {
    Normal = 0,
    Batch = 3,
    Idle = 5,
}

/// Set the priority to zero in the caller's current scheduling policy.
pub fn sched_setparam() -> Result<(), SyscallError> {
    let priority = 0_i32;
    decode_zero(unsafe {
        abi::invoke(
            SCHED_SETPARAM,
            [0, std::ptr::from_ref(&priority) as usize, 0, 0, 0, 0],
        )
    })
}

/// Select one of the ordinary Linux scheduling policies for the current thread.
pub fn sched_setscheduler(policy: SchedulerPolicy) -> Result<(), SyscallError> {
    let priority = 0_i32;
    decode_zero(unsafe {
        abi::invoke(
            SCHED_SETSCHEDULER,
            [
                0,
                policy as usize,
                std::ptr::from_ref(&priority) as usize,
                0,
                0,
                0,
            ],
        )
    })
}

#[repr(C)]
struct NativeSchedulerAttributes {
    size: u32,
    policy: u32,
    flags: u64,
    nice: i32,
    priority: u32,
    runtime: u64,
    deadline: u64,
    period: u64,
}

const _: () = {
    assert!(std::mem::size_of::<NativeSchedulerAttributes>() == 48);
    assert!(std::mem::offset_of!(NativeSchedulerAttributes, nice) == 16);
    assert!(std::mem::offset_of!(NativeSchedulerAttributes, runtime) == 24);
};

/// Request an ordinary policy and nonnegative nice value via the version-0
/// sched_attr layout. Linux may reject a priority increase for this caller.
pub fn sched_setattr(policy: SchedulerPolicy, nice: i32) -> Result<(), SyscallError> {
    if !(0..=19).contains(&nice) {
        return Err(SyscallError::InvalidInput("nice must be 0 through 19"));
    }
    let attributes = NativeSchedulerAttributes {
        size: std::mem::size_of::<NativeSchedulerAttributes>() as u32,
        policy: policy as u32,
        flags: 0,
        nice,
        priority: 0,
        runtime: 0,
        deadline: 0,
        period: 0,
    };
    decode_zero(unsafe {
        abi::invoke(
            SCHED_SETATTR,
            [0, std::ptr::from_ref(&attributes) as usize, 0, 0, 0, 0],
        )
    })
}
