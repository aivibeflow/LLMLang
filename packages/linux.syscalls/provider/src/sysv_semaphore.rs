//! Native System V semaphores for private, owned sets in one IPC namespace.

use super::{abi, decode_nonnegative, decode_zero, SyscallError, Timespec};
use std::fmt;
use std::mem::{align_of, offset_of, size_of};
use std::ptr;

const SEMGET: usize = 64;
const SEMOP: usize = 65;
const SEMCTL: usize = 66;
const SEMTIMEDOP: usize = 220;
const IPC_PRIVATE: usize = 0;
const IPC_CREAT: usize = 0o1000;
const IPC_RMID: usize = 0;
const GETVAL: usize = 12;
const SETVAL: usize = 16;
const SEMVMX: usize = 32_767;
const MAX_SEMAPHORES: u32 = u16::MAX as u32 + 1;

/// Owns a newly created set. No existing semaphore identifier can be attached.
/// Keep the owner and its borrows in the IPC namespace that created it.
/// Dropping attempts removal. Abnormal process exit can leave the set allocated.
#[derive(Debug)]
#[must_use = "dropping the semaphore set attempts removal"]
pub struct SemaphoreSet {
    id: i32,
    count: u32,
}

impl SemaphoreSet {
    pub fn count(&self) -> u32 {
        self.count
    }

    fn check_index(&self, index: u16) -> Result<(), SyscallError> {
        if u32::from(index) >= self.count {
            return Err(SyscallError::InvalidInput(
                "semaphore index outside the owned set",
            ));
        }
        Ok(())
    }
}

impl Drop for SemaphoreSet {
    fn drop(&mut self) {
        let _ = remove_id(self.id);
    }
}

/// Creates one IPC_PRIVATE set of initially zero semaphores. The native kernel
/// may enforce a lower per-set count or namespace resource limit.
pub fn semget(count: u32, permissions: u16) -> Result<SemaphoreSet, SyscallError> {
    if !(1..=MAX_SEMAPHORES).contains(&count) {
        return Err(SyscallError::InvalidInput(
            "semaphore count outside the native index space",
        ));
    }
    if permissions > 0o777 {
        return Err(SyscallError::InvalidInput(
            "semaphore mode must contain only permission bits",
        ));
    }
    let raw = unsafe {
        abi::invoke(
            SEMGET,
            [
                IPC_PRIVATE,
                count as usize,
                IPC_CREAT | permissions as usize,
                0,
                0,
                0,
            ],
        )
    };
    let id =
        i32::try_from(decode_nonnegative(raw)?).map_err(|_| SyscallError::UnexpectedReturn(raw))?;
    Ok(SemaphoreSet { id, count })
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(i16)]
pub enum SemaphoreMode {
    Wait = 0,
    NoWait = 0o4000,
}

/// A native x86-64 sembuf. A negative delta decrements, zero waits for zero,
/// and a positive delta increments. The kernel only reads the array.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(C)]
pub struct SemaphoreOperation {
    pub index: u16,
    pub delta: i16,
    pub mode: SemaphoreMode,
}

const _: () = {
    assert!(size_of::<SemaphoreOperation>() == 6);
    assert!(align_of::<SemaphoreOperation>() == 2);
    assert!(offset_of!(SemaphoreOperation, delta) == 2);
    assert!(offset_of!(SemaphoreOperation, mode) == 4);
};

/// Applies the complete ordered operation vector atomically. The per-operation
/// NoWait mode returns EAGAIN when the operation would block.
pub fn semop(set: &SemaphoreSet, operations: &[SemaphoreOperation]) -> Result<(), SyscallError> {
    operate(SEMOP, set, operations, None)
}

/// Like semop, with an optional relative timeout. On expiration Linux returns
/// EAGAIN and applies none of the operations. Interruption is returned unchanged.
pub fn semtimedop(
    set: &SemaphoreSet,
    operations: &[SemaphoreOperation],
    timeout: Option<Timespec>,
) -> Result<(), SyscallError> {
    operate(SEMTIMEDOP, set, operations, timeout.as_ref())
}

fn operate(
    syscall: usize,
    set: &SemaphoreSet,
    operations: &[SemaphoreOperation],
    timeout: Option<&Timespec>,
) -> Result<(), SyscallError> {
    let count = u32::try_from(operations.len())
        .ok()
        .filter(|count| *count > 0)
        .ok_or(SyscallError::InvalidInput(
            "semaphore operations must fit a nonempty native array",
        ))?;
    for operation in operations {
        set.check_index(operation.index)?;
    }
    let timeout_ptr = timeout.map_or(ptr::null(), ptr::from_ref);
    let raw = unsafe {
        abi::invoke(
            syscall,
            [
                set.id as usize,
                operations.as_ptr() as usize,
                count as usize,
                timeout_ptr as usize,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)
}

pub fn semctl_getval(set: &SemaphoreSet, index: u16) -> Result<u16, SyscallError> {
    set.check_index(index)?;
    let raw = semctl(set.id, index, GETVAL, 0);
    let value = decode_nonnegative(raw)?;
    if value > SEMVMX {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    Ok(value as u16)
}

/// Sets one value. Native Linux rejects values over SEMVMX with ERANGE.
pub fn semctl_setval(set: &SemaphoreSet, index: u16, value: u16) -> Result<(), SyscallError> {
    set.check_index(index)?;
    decode_zero(semctl(set.id, index, SETVAL, value as usize))
}

#[derive(Debug)]
pub struct SemaphoreRemoveError {
    error: SyscallError,
    set: SemaphoreSet,
}

impl SemaphoreRemoveError {
    pub fn into_parts(self) -> (SyscallError, SemaphoreSet) {
        (self.error, self.set)
    }
}

impl fmt::Display for SemaphoreRemoveError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "semctl IPC_RMID: {}", self.error)
    }
}

impl std::error::Error for SemaphoreRemoveError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        Some(&self.error)
    }
}

/// Removes the kernel set. Success consumes the owner and error returns it.
pub fn semctl_remove(set: SemaphoreSet) -> Result<(), SemaphoreRemoveError> {
    match remove_id(set.id) {
        Ok(()) => {
            std::mem::forget(set);
            Ok(())
        }
        Err(error) => Err(SemaphoreRemoveError { error, set }),
    }
}

fn remove_id(id: i32) -> Result<(), SyscallError> {
    decode_zero(semctl(id, 0, IPC_RMID, 0))
}

fn semctl(id: i32, index: u16, command: usize, argument: usize) -> isize {
    // The supported commands either use no union argument or pass SETVAL's
    // integer by value in the native little-endian user ABI.
    unsafe {
        abi::invoke(
            SEMCTL,
            [id as usize, index as usize, command, argument, 0, 0],
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::EINVAL;

    #[test]
    fn semaphore_set_removal_and_drop_release_owned_ids() {
        let explicit = semget(1, 0o600).unwrap();
        let id = explicit.id;
        semctl_remove(explicit).unwrap();
        assert!(decode_nonnegative(semctl(id, 0, GETVAL, 0))
            .unwrap_err()
            .is_errno(EINVAL));

        let implicit = semget(1, 0o600).unwrap();
        let id = implicit.id;
        drop(implicit);
        assert!(decode_nonnegative(semctl(id, 0, GETVAL, 0))
            .unwrap_err()
            .is_errno(EINVAL));
    }
}
