//! Read-only remapping within one owned scratch memfd.

use crate::{abi, decode_nonnegative, decode_zero, files_extra2::memfd_create_with_flags};
use crate::{write, SyscallError, EINTR};
use std::{fmt, os::fd::AsRawFd, ptr::NonNull, slice};

const REMAP_FILE_PAGES: usize = 216;
const MAP_SHARED: usize = 1;
const PROT_READ: usize = 1;
const MFD_ALLOW_SEALING: usize = 0x0002;
const MFD_NOEXEC_SEAL: usize = 0x0008;
const F_ADD_SEALS: usize = 1033;
const F_SEAL_SEAL: usize = 0x0001;
const F_SEAL_SHRINK: usize = 0x0002;
const F_SEAL_GROW: usize = 0x0004;
const F_SEAL_FUTURE_WRITE: usize = 0x0010;

/// Native x86-64 base page size for the remapping profile.
pub const FILE_MAPPING_PAGE_SIZE: usize = 4096;

type FilePage = [u8; FILE_MAPPING_PAGE_SIZE];

/// Owns one readable page mapped over an immutable scratch file. The page
/// is always within the file. The address and descriptor remain private.
pub struct FilePageMapping {
    address: NonNull<u8>,
    file_pages: usize,
}

impl FilePageMapping {
    pub fn as_slice(&self) -> &[u8] {
        // The memfd was completely initialized and sealed before the first map.
        // A remap consumes the owner, so this borrow cannot span a remap.
        unsafe { slice::from_raw_parts(self.address.as_ptr(), FILE_MAPPING_PAGE_SIZE) }
    }
}

impl fmt::Debug for FilePageMapping {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("FilePageMapping")
            .field("file_pages", &self.file_pages)
            .finish_non_exhaustive()
    }
}

impl Drop for FilePageMapping {
    fn drop(&mut self) {
        let _ = unsafe {
            abi::invoke(
                abi::MUNMAP,
                [
                    self.address.as_ptr() as usize,
                    FILE_MAPPING_PAGE_SIZE,
                    0,
                    0,
                    0,
                    0,
                ],
            )
        };
    }
}

/// Creates a read-only mapping of the first page of an immutable scratch file.
pub fn create_file_page_mapping(pages: &[FilePage]) -> Result<FilePageMapping, SyscallError> {
    if pages.is_empty() {
        return Err(SyscallError::InvalidInput(
            "file page mapping must contain a page",
        ));
    }
    let fd = memfd_create_with_flags(c"llmlang-file-page", MFD_ALLOW_SEALING | MFD_NOEXEC_SEAL)?;
    for page in pages {
        let mut remaining: &[u8] = page;
        while !remaining.is_empty() {
            match write(fd.borrow(), remaining) {
                Ok(0) => return Err(SyscallError::UnexpectedReturn(0)),
                Ok(progress) => remaining = &remaining[progress..],
                Err(error) if error.is_errno(EINTR) => continue,
                Err(error) => return Err(error),
            }
        }
    }
    // There are no pre-existing shared mappings of this scratch file. The
    // future-write seal bars writes and writable mappings while allowing the
    // read-only MAP_SHARED mapping required by remap_file_pages.
    let raw = unsafe {
        abi::invoke(
            abi::FCNTL,
            [
                fd.as_raw_fd() as usize,
                F_ADD_SEALS,
                F_SEAL_SEAL | F_SEAL_SHRINK | F_SEAL_GROW | F_SEAL_FUTURE_WRITE,
                0,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)?;
    let raw = unsafe {
        abi::invoke(
            abi::MMAP,
            [
                0,
                FILE_MAPPING_PAGE_SIZE,
                PROT_READ,
                MAP_SHARED,
                fd.as_raw_fd() as usize,
                0,
            ],
        )
    };
    let base = decode_nonnegative(raw)?;
    let Some(address) = NonNull::new(base as *mut u8) else {
        let _ = unsafe { abi::invoke(abi::MUNMAP, [base, FILE_MAPPING_PAGE_SIZE, 0, 0, 0, 0]) };
        return Err(SyscallError::UnexpectedReturn(raw));
    };
    Ok(FilePageMapping {
        address,
        file_pages: pages.len(),
    })
}

/// Replaces the whole owned virtual page with the given scratch-file page.
/// Linux may release the old address on a late MAP_FIXED failure. The consumed
/// owner can clean up the address only after success establishes ownership.
pub fn remap_file_pages(
    mapping: FilePageMapping,
    file_page: usize,
) -> Result<FilePageMapping, SyscallError> {
    if file_page >= mapping.file_pages {
        return Err(SyscallError::InvalidInput(
            "file page index is outside the scratch file",
        ));
    }
    let mapping = std::mem::ManuallyDrop::new(mapping);
    let raw = unsafe {
        abi::invoke(
            REMAP_FILE_PAGES,
            [
                mapping.address.as_ptr() as usize,
                FILE_MAPPING_PAGE_SIZE,
                0,
                file_page,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)?;
    Ok(std::mem::ManuallyDrop::into_inner(mapping))
}
