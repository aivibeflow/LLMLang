use super::{abi, decode_write, decode_zero, Directory, SyscallError};
use std::ffi::CStr;
use std::os::fd::{AsRawFd, BorrowedFd};

const GETDENTS: usize = 78;
const MKNOD: usize = 133;
const MKNODAT: usize = 259;
const FCHMODAT: usize = 268;
const S_IFIFO: usize = 0o010000;
const PERMISSION_BITS: u16 = 0o7777;
const DIR_NAME_OFFSET: usize = 18;
const RECORD_ALIGNMENT: usize = 8;

/// Creates a FIFO at a pathname, subject to the Linux umask and filesystem
/// permission rules. The node type is fixed and the device argument is zero.
pub fn mknod(path: &CStr, permissions: u16) -> Result<(), SyscallError> {
    let mode = fifo_mode(permissions)?;
    decode_zero(unsafe { abi::call(MKNOD, [path.as_ptr() as usize, mode, 0, 0, 0, 0]) })
}

/// Creates a FIFO at a path relative to the selected directory.
pub fn mknodat(dir: Directory<'_>, path: &CStr, permissions: u16) -> Result<(), SyscallError> {
    let mode = fifo_mode(permissions)?;
    decode_zero(unsafe {
        abi::call(
            MKNODAT,
            [dir.argument(), path.as_ptr() as usize, mode, 0, 0, 0],
        )
    })
}

fn fifo_mode(permissions: u16) -> Result<usize, SyscallError> {
    if permissions & !PERMISSION_BITS != 0 {
        return Err(SyscallError::InvalidInput(
            "FIFO mode must contain only Linux permission bits",
        ));
    }
    Ok(S_IFIFO | permissions as usize)
}

/// Sets mode bits for a directory-relative pathname. The native three-argument
/// Linux ABI follows a final symlink and has no flags argument.
pub fn fchmodat(dir: Directory<'_>, path: &CStr, mode: u16) -> Result<(), SyscallError> {
    decode_zero(unsafe {
        abi::call(
            FCHMODAT,
            [
                dir.argument(),
                path.as_ptr() as usize,
                mode as usize,
                0,
                0,
                0,
            ],
        )
    })
}

/// One native x86-64 legacy directory record, with an opaque position cookie.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct LegacyDirectoryEntry<'a> {
    pub inode: u64,
    pub next_offset: u64,
    pub kind: u8,
    pub name: &'a CStr,
}

/// Reads and decodes one legacy Linux directory batch. Each record stores
/// its type in the last byte; names borrow the provided buffer. A successful
/// empty batch marks the end of the directory.
pub fn getdents<'a>(
    fd: BorrowedFd<'_>,
    buffer: &'a mut [u8],
) -> Result<Vec<LegacyDirectoryEntry<'a>>, SyscallError> {
    let capacity = u32::try_from(buffer.len()).map_err(|_| {
        SyscallError::InvalidInput("directory buffer capacity exceeds Linux unsigned int")
    })?;
    let raw = unsafe {
        abi::call(
            GETDENTS,
            [
                fd.as_raw_fd() as usize,
                buffer.as_mut_ptr() as usize,
                capacity as usize,
                0,
                0,
                0,
            ],
        )
    };
    let length = decode_write(raw, buffer.len())?;
    decode_dirents(&buffer[..length]).ok_or(SyscallError::UnexpectedReturn(raw))
}

fn decode_dirents(mut bytes: &[u8]) -> Option<Vec<LegacyDirectoryEntry<'_>>> {
    // Linux v6.12 `fs/readdir.c` defines the header and trailing d_type byte.
    let mut records = Vec::new();
    while !bytes.is_empty() {
        let inode = u64::from_ne_bytes(bytes.get(..8)?.try_into().ok()?);
        let next_offset = u64::from_ne_bytes(bytes.get(8..16)?.try_into().ok()?);
        let length = u16::from_ne_bytes(bytes.get(16..DIR_NAME_OFFSET)?.try_into().ok()?) as usize;
        if length <= DIR_NAME_OFFSET + 1 || length % RECORD_ALIGNMENT != 0 {
            return None;
        }
        let (record, remaining) = bytes.split_at_checked(length)?;
        let kind = record[length - 1];
        let name = CStr::from_bytes_until_nul(&record[DIR_NAME_OFFSET..length - 1]).ok()?;
        if name.to_bytes().is_empty() {
            return None;
        }
        records.push(LegacyDirectoryEntry {
            inode,
            next_offset,
            kind,
            name,
        });
        bytes = remaining;
    }
    Some(records)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn legacy_decoder_validates_name_and_type_boundaries() {
        let mut record = [0xff_u8; 24];
        record[..8].copy_from_slice(&7_u64.to_ne_bytes());
        record[8..16].copy_from_slice(&u64::MAX.to_ne_bytes());
        record[16..18].copy_from_slice(&24_u16.to_ne_bytes());
        record[18..21].copy_from_slice(b"ok\0");
        record[23] = 8;
        assert_eq!(
            decode_dirents(&record).unwrap(),
            [LegacyDirectoryEntry {
                inode: 7,
                next_offset: u64::MAX,
                kind: 8,
                name: c"ok"
            }]
        );
        assert!(decode_dirents(&record[..23]).is_none());
        record[20] = b'x';
        record[23] = 0;
        assert!(decode_dirents(&record).is_none()); // Type byte is never a name terminator.
        record[16..18].copy_from_slice(&23_u16.to_ne_bytes());
        assert!(decode_dirents(&record).is_none());
    }
}
