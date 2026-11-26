use super::{abi, decode_zero, Mapping, SyscallError};

const MSYNC: usize = 26;
const MINCORE: usize = 27;
const MLOCK: usize = 149;
const MUNLOCK: usize = 150;
const MLOCK2: usize = 325;
const PAGE_SIZE: usize = 4096;

fn memory_call(operation: usize, mapping: &Mapping, third: usize) -> Result<(), SyscallError> {
    let bytes = mapping.as_slice();
    let raw = unsafe {
        abi::invoke(
            operation,
            [bytes.as_ptr() as usize, bytes.len(), third, 0, 0, 0],
        )
    };
    decode_zero(raw)
}

/// Locks the mapping's native page-rounded range and makes its pages resident
/// on success. Linux enforces the caller's lock limit and privileges.
pub fn mlock(mapping: &mut Mapping) -> Result<(), SyscallError> {
    memory_call(MLOCK, mapping, 0)
}

/// Releases memory locks across the entire mapping. Linux does not count
/// repeated locks of a page as independent references.
pub fn munlock(mapping: &mut Mapping) -> Result<(), SyscallError> {
    memory_call(MUNLOCK, mapping, 0)
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum MemoryLockMode {
    Immediate = 0,
    OnFault = 1,
}

/// Locks memory immediately or locks resident pages now and other pages when
/// they become resident. Both modes apply to the whole owned mapping.
pub fn mlock2(mapping: &mut Mapping, mode: MemoryLockMode) -> Result<(), SyscallError> {
    memory_call(MLOCK2, mapping, mode as usize)
}

/// Samples one residency bit per native 4096-byte page in the mapping.
/// The sample can become stale immediately. On success the first returned
/// count of output bytes are normalized to 0 or 1. The suffix is untouched.
/// A kernel error can leave the vector prefix partially written.
pub fn mincore(mapping: &Mapping, residency: &mut [u8]) -> Result<usize, SyscallError> {
    let pages = mapping.as_slice().len().div_ceil(PAGE_SIZE);
    if residency.len() < pages {
        return Err(SyscallError::InvalidInput(
            "mincore output requires one byte per mapping page",
        ));
    }
    memory_call(MINCORE, mapping, residency.as_mut_ptr() as usize)?;
    for byte in &mut residency[..pages] {
        *byte &= 1;
    }
    Ok(pages)
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum MemorySyncMode {
    Asynchronous = 1,
    Synchronous = 4,
    AsynchronousInvalidate = 1 | 2,
    SynchronousInvalidate = 4 | 2,
}

/// Requests synchronization on the owned private anonymous mapping. There is
/// no backing file to persist. Invalidation can fail with EBUSY while locked.
pub fn msync(mapping: &mut Mapping, mode: MemorySyncMode) -> Result<(), SyscallError> {
    memory_call(MSYNC, mapping, mode as usize)
}
