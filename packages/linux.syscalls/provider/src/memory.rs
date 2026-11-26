use super::{abi, decode_nonnegative, decode_zero, SyscallError};
use std::{fmt, ptr::NonNull, slice};

const MAP_PRIVATE_ANONYMOUS: usize = 0x02 | 0x20;
const MREMAP: usize = 25;
const MREMAP_MAYMOVE: usize = 1;
const PKEY_MPROTECT: usize = 329;
const MAP_SHADOW_STACK: usize = 453;
const PKEY_ALLOC: usize = 330;
const PKEY_FREE: usize = 331;

/// The profile requests readable mappings and never requests PROT_EXEC.
/// The deployment assumes a Linux process without READ_IMPLIES_EXEC.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Protection {
    ReadOnly = 0x1,
    ReadWrite = 0x3,
}

/// Page advice limited to local private anonymous mappings.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Advice {
    Normal = 0,
    Random = 1,
    Sequential = 2,
    WillNeed = 3,
    DontNeed = 4,
}

/// Owns a private anonymous region in the current process. Its byte slices
/// cover the requested length, excluding any extra bytes from page rounding.
pub struct Mapping {
    address: NonNull<u8>,
    length: usize,
    writable: bool,
}

impl Mapping {
    pub fn as_slice(&self) -> &[u8] {
        // Every admitted protection permits reads. The range remains mapped
        // until the owner is consumed or dropped, and all bytes are initialized.
        unsafe { slice::from_raw_parts(self.address.as_ptr(), self.length) }
    }

    pub fn as_mut_slice(&mut self) -> Option<&mut [u8]> {
        if !self.writable {
            return None;
        }
        // The exclusive borrow rules out conflicting slices or permission changes.
        Some(unsafe { slice::from_raw_parts_mut(self.address.as_ptr(), self.length) })
    }
}

impl fmt::Debug for Mapping {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("Mapping")
            .field("length", &self.length)
            .field("writable", &self.writable)
            .finish_non_exhaustive()
    }
}

impl Drop for Mapping {
    fn drop(&mut self) {
        if self.length != 0 {
            let _ = unmap(self.address.as_ptr() as usize, self.length);
        }
    }
}

/// Owns a private shadow-stack mapping whose lifetime ends on drop.
#[derive(Debug)]
pub struct ShadowStack(Mapping);

impl ShadowStack {
    pub fn as_slice(&self) -> &[u8] {
        self.0.as_slice()
    }
}

/// Maps a shadow stack at a kernel-selected address without a restore token.
/// The returned range can be read and is never installed as the active stack.
pub fn map_shadow_stack(length: usize) -> Result<ShadowStack, SyscallError> {
    check_mapping_length(length)?;
    let raw = unsafe { abi::call(MAP_SHADOW_STACK, [0, length, 0, 0, 0, 0]) };
    let base = decode_nonnegative(raw)?;
    let Some(address) = nonnull_range(base, length) else {
        let _ = unmap(base, length);
        return Err(SyscallError::UnexpectedReturn(raw));
    };
    Ok(ShadowStack(Mapping {
        address,
        length,
        writable: false,
    }))
}

fn check_mapping_length(length: usize) -> Result<(), SyscallError> {
    if length == 0 || length > isize::MAX as usize {
        return Err(SyscallError::InvalidInput(
            "mapping length must be in 1..=isize::MAX",
        ));
    }
    Ok(())
}

fn nonnull_range(base: usize, length: usize) -> Option<NonNull<u8>> {
    NonNull::new(base as *mut u8).filter(|_| base.checked_add(length).is_some())
}

/// Creates a zero-initialized mapping with kernel-selected address and the
/// requested read or read-write protection.
pub fn mmap(length: usize, protection: Protection) -> Result<Mapping, SyscallError> {
    check_mapping_length(length)?;
    let raw = unsafe {
        abi::call(
            abi::MMAP,
            [
                0,
                length,
                protection as usize,
                MAP_PRIVATE_ANONYMOUS,
                usize::MAX,
                0,
            ],
        )
    };
    let base = decode_nonnegative(raw)?;
    let Some(address) = nonnull_range(base, length) else {
        let _ = unmap(base, length);
        return Err(SyscallError::UnexpectedReturn(raw));
    };
    Ok(Mapping {
        address,
        length,
        writable: protection == Protection::ReadWrite,
    })
}

/// Resizes the whole anonymous region, allowing Linux to relocate it. The
/// exclusive borrow excludes live slices while the address can change.
/// A kernel error leaves the original mapping usable with its old length.
/// On success the retained pages keep their bytes and newly allocated pages
/// read as zero. Bytes hidden by a page-rounded shrink can reappear on regrowth.
pub fn mremap(mapping: &mut Mapping, new_length: usize) -> Result<(), SyscallError> {
    check_mapping_length(new_length)?;
    if mapping.length == 0 {
        return Err(SyscallError::InvalidInput("mapping has no live region"));
    }
    let raw = unsafe {
        abi::call(
            MREMAP,
            [
                mapping.address.as_ptr() as usize,
                mapping.length,
                new_length,
                MREMAP_MAYMOVE,
                0,
                0,
            ],
        )
    };
    let base = decode_nonnegative(raw)?;
    let Some(address) = nonnull_range(base, new_length) else {
        // After native success the old address may already be gone. An
        // unsupported replacement cannot be exposed as a Rust slice.
        mapping.address = NonNull::dangling();
        mapping.length = 0;
        mapping.writable = false;
        let _ = unmap(base, new_length);
        return Err(SyscallError::UnexpectedReturn(raw));
    };
    mapping.address = address;
    mapping.length = new_length;
    Ok(())
}

/// Changes protection across the entire mapping. A failed call disables
/// mutable borrows until a subsequent read-write change succeeds.
pub fn mprotect(mapping: &mut Mapping, protection: Protection) -> Result<(), SyscallError> {
    set_protection(mapping, protection, abi::MPROTECT)
}

/// Changes read/write protection across the owned mapping using the default
/// protection key (0). A failure disables mutable borrows.
pub fn pkey_mprotect(mapping: &mut Mapping, protection: Protection) -> Result<(), SyscallError> {
    set_protection(mapping, protection, PKEY_MPROTECT)
}

fn set_protection(
    mapping: &mut Mapping,
    protection: Protection,
    syscall: usize,
) -> Result<(), SyscallError> {
    mapping.writable = false;
    let raw = unsafe {
        abi::call(
            syscall,
            [
                mapping.address.as_ptr() as usize,
                mapping.length,
                protection as usize,
                0,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)?;
    mapping.writable = protection == Protection::ReadWrite;
    Ok(())
}

/// Advises the kernel about the complete region. Successful `DontNeed` on
/// this private anonymous mapping discards its current data. Reads refault zeros.
pub fn madvise(mapping: &mut Mapping, advice: Advice) -> Result<(), SyscallError> {
    let raw = unsafe {
        abi::call(
            abi::MADVISE,
            [
                mapping.address.as_ptr() as usize,
                mapping.length,
                advice as usize,
                0,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)
}

/// A failed explicit release returns responsibility for the mapping.
#[derive(Debug)]
pub struct UnmapError {
    error: SyscallError,
    mapping: Mapping,
}

impl UnmapError {
    pub fn into_parts(self) -> (SyscallError, Mapping) {
        (self.error, self.mapping)
    }
}

impl fmt::Display for UnmapError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "munmap: {}", self.error)
    }
}

impl std::error::Error for UnmapError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        Some(&self.error)
    }
}

/// Releases the mapping. A failed syscall transfers the still-owned range
/// into the error, so the caller can retry or let the owner's drop path run.
pub fn munmap(mapping: Mapping) -> Result<(), UnmapError> {
    if mapping.length == 0 {
        return Ok(());
    }
    match unmap(mapping.address.as_ptr() as usize, mapping.length) {
        Ok(()) => {
            std::mem::forget(mapping);
            Ok(())
        }
        Err(error) => Err(UnmapError { error, mapping }),
    }
}

fn unmap(address: usize, length: usize) -> Result<(), SyscallError> {
    decode_zero(unsafe { abi::call(abi::MUNMAP, [address, length, 0, 0, 0, 0]) })
}

/// Owns a non-default protection key in this address space. The profile
/// never associates such a key with a mapping. Code outside the profile must
/// leave its allocation untouched while this token exists.
#[derive(Debug)]
pub struct ProtectionKey {
    index: u8,
}

impl Drop for ProtectionKey {
    fn drop(&mut self) {
        let _ = release_key(self.index);
    }
}

/// Allocate one unused key. Flags and initial access restrictions are zero.
pub fn pkey_alloc() -> Result<ProtectionKey, SyscallError> {
    let raw = unsafe { abi::call(PKEY_ALLOC, [0; 6]) };
    let index = decode_nonnegative(raw)?;
    if !(1..=15).contains(&index) {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    Ok(ProtectionKey { index: index as u8 })
}

/// A failed explicit release leaves responsibility for the key in the error.
#[derive(Debug)]
pub struct ProtectionKeyReleaseError {
    error: SyscallError,
    key: ProtectionKey,
}

impl ProtectionKeyReleaseError {
    pub fn into_parts(self) -> (SyscallError, ProtectionKey) {
        (self.error, self.key)
    }
}

impl fmt::Display for ProtectionKeyReleaseError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "pkey_free: {}", self.error)
    }
}

impl std::error::Error for ProtectionKeyReleaseError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        Some(&self.error)
    }
}

/// Release the owned key. A failed syscall returns ownership for a retry
/// or best-effort release on drop.
pub fn pkey_free(key: ProtectionKey) -> Result<(), ProtectionKeyReleaseError> {
    match release_key(key.index) {
        Ok(()) => {
            std::mem::forget(key);
            Ok(())
        }
        Err(error) => Err(ProtectionKeyReleaseError { error, key }),
    }
}

fn release_key(index: u8) -> Result<(), SyscallError> {
    decode_zero(unsafe { abi::call(PKEY_FREE, [usize::from(index), 0, 0, 0, 0, 0]) })
}
