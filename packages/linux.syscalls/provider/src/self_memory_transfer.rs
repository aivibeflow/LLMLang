use crate::{abi, decode_write, decode_zero, getpid, SyscallError};

const PROCESS_VM_READV: usize = 310;
const PROCESS_VM_WRITEV: usize = 311;
const SCHED_GETATTR: usize = 315;
const SCHED_ATTR_SIZE_VER0: usize = 48;

/// Native x86-64 layout used by both process_vm syscalls. Keeping the
/// descriptors on the stack avoids allocation for this single-vector profile.
#[repr(C)]
struct Iovec {
    base: usize,
    length: usize,
}

const _: () = {
    assert!(std::mem::size_of::<Iovec>() == 16);
    assert!(std::mem::align_of::<Iovec>() == 8);
    assert!(std::mem::offset_of!(Iovec, length) == 8);
};

fn self_transfer(number: usize, local: Iovec, remote: Iovec) -> Result<usize, SyscallError> {
    let pid = getpid()? as usize;
    let limit = local.length.min(remote.length);

    // The two live, disjoint borrows define the complete memory footprint.
    // Pid is fixed to this process, the vectors stay on the stack until the
    // synchronous kernel copy returns, and flags are zero.
    let raw = unsafe {
        abi::call(
            number,
            [
                pid,
                std::ptr::from_ref(&local) as usize,
                1,
                std::ptr::from_ref(&remote) as usize,
                1,
                0,
            ],
        )
    };
    decode_write(raw, limit)
}

/// Copy a prefix from a shared source borrow in the current process into
/// an exclusive destination borrow. This profile has no remote process or
/// address parameter and reports the actual native byte count.
///
/// ```compile_fail
/// use linux_syscalls_provider::process_vm_readv;
/// let mut bytes = [1, 2];
/// process_vm_readv(&bytes, &mut bytes).unwrap();
/// ```
pub fn process_vm_readv(source: &[u8], destination: &mut [u8]) -> Result<usize, SyscallError> {
    self_transfer(
        PROCESS_VM_READV,
        Iovec {
            base: destination.as_mut_ptr() as usize,
            length: destination.len(),
        },
        Iovec {
            base: source.as_ptr() as usize,
            length: source.len(),
        },
    )
}

/// Copy a prefix from a shared source borrow in the current process into
/// an exclusive destination borrow via the native writev argument order.
/// The destination tail after the returned count retains its prior contents.
pub fn process_vm_writev(source: &[u8], destination: &mut [u8]) -> Result<usize, SyscallError> {
    self_transfer(
        PROCESS_VM_WRITEV,
        Iovec {
            base: source.as_ptr() as usize,
            length: source.len(),
        },
        Iovec {
            base: destination.as_mut_ptr() as usize,
            length: destination.len(),
        },
    )
}

#[derive(Default)]
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
    assert!(std::mem::size_of::<NativeSchedulerAttributes>() == SCHED_ATTR_SIZE_VER0);
    assert!(std::mem::align_of::<NativeSchedulerAttributes>() == 8);
    assert!(std::mem::offset_of!(NativeSchedulerAttributes, flags) == 8);
    assert!(std::mem::offset_of!(NativeSchedulerAttributes, period) == 40);
};

/// A snapshot of the base Linux scheduler attributes for the calling thread.
/// Numeric policy and flag fields are the raw v0 UAPI values.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct SchedulerAttributes {
    pub policy: u32,
    pub flags: u64,
    pub nice: i32,
    pub priority: u32,
    pub runtime: u64,
    pub deadline: u64,
    pub period: u64,
}

/// Observe the base scheduler record for the calling thread (PID encoded as
/// zero). No utilization hints or other scheduler extensions are requested.
pub fn sched_getattr() -> Result<SchedulerAttributes, SyscallError> {
    let mut native = NativeSchedulerAttributes::default();
    let raw = unsafe {
        abi::call(
            SCHED_GETATTR,
            [
                0,
                std::ptr::from_mut(&mut native) as usize,
                SCHED_ATTR_SIZE_VER0,
                0,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)?;
    if native.size as usize != SCHED_ATTR_SIZE_VER0 {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    Ok(SchedulerAttributes {
        policy: native.policy,
        flags: native.flags,
        nice: native.nice,
        priority: native.priority,
        runtime: native.runtime,
        deadline: native.deadline,
        period: native.period,
    })
}
