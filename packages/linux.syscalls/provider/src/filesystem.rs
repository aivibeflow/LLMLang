use super::{abi, decode_write, decode_zero, Directory, SyscallError};
use std::ffi::CStr;
use std::os::fd::{AsRawFd, BorrowedFd};

const STATX_TYPE: u32 = 0x001;
const STATX_MODE: u32 = 0x002;
const STATX_NLINK: u32 = 0x004;
const STATX_UID: u32 = 0x008;
const STATX_GID: u32 = 0x010;
const STATX_ATIME: u32 = 0x020;
const STATX_MTIME: u32 = 0x040;
const STATX_CTIME: u32 = 0x080;
const STATX_INO: u32 = 0x100;
const STATX_SIZE: u32 = 0x200;
const STATX_BLOCKS: u32 = 0x400;
const STATX_BASIC_STATS: u32 = 0x7ff;
const STATX_BTIME: u32 = 0x800;
const S_IFMT: u16 = 0o170000;

#[repr(C)]
#[derive(Clone, Copy, Default)]
struct NativeTimestamp {
    seconds: i64,
    nanos: u32,
    reserved: i32,
}

#[repr(C)]
#[derive(Default)]
struct NativeStatx {
    mask: u32,
    block_size: u32,
    attributes: u64,
    links: u32,
    uid: u32,
    gid: u32,
    mode: u16,
    reserved: u16,
    inode: u64,
    size: u64,
    blocks: u64,
    attributes_mask: u64,
    accessed: NativeTimestamp,
    created: NativeTimestamp,
    changed: NativeTimestamp,
    modified: NativeTimestamp,
    special_dev_major: u32,
    special_dev_minor: u32,
    dev_major: u32,
    dev_minor: u32,
    extensions: [u64; 14],
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct FileTimestamp {
    seconds: i64,
    nanos: u32,
}

impl FileTimestamp {
    pub fn seconds(self) -> i64 {
        self.seconds
    }

    pub fn nanos(self) -> u32 {
        self.nanos
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct FileMetadata {
    pub returned_mask: u32,
    pub inode: Option<u64>,
    pub size: Option<u64>,
    pub blocks: Option<u64>,
    pub links: Option<u32>,
    pub uid: Option<u32>,
    pub gid: Option<u32>,
    pub file_type: Option<u16>,
    pub permissions: Option<u16>,
    pub accessed: Option<FileTimestamp>,
    pub created: Option<FileTimestamp>,
    pub changed: Option<FileTimestamp>,
    pub modified: Option<FileTimestamp>,
}

fn available<T>(mask: u32, flag: u32, value: T) -> Option<T> {
    (mask & flag != 0).then_some(value)
}

fn timestamp(
    mask: u32,
    flag: u32,
    value: NativeTimestamp,
) -> Result<Option<FileTimestamp>, SyscallError> {
    if mask & flag == 0 {
        return Ok(None);
    }
    if value.nanos >= 1_000_000_000 {
        return Err(SyscallError::UnexpectedReturn(0));
    }
    Ok(Some(FileTimestamp {
        seconds: value.seconds,
        nanos: value.nanos,
    }))
}

/// Requests the Linux basic stat fields and creation time. The returned mask
/// distinguishes available data from kernel-supplied placeholder fields.
pub fn statx(dir: Directory<'_>, path: &CStr, flags: i32) -> Result<FileMetadata, SyscallError> {
    let mut result = NativeStatx::default();
    let raw = unsafe {
        abi::call(
            abi::STATX,
            [
                dir.argument(),
                path.as_ptr() as usize,
                flags as usize,
                (STATX_BASIC_STATS | STATX_BTIME) as usize,
                (&mut result as *mut NativeStatx) as usize,
                0,
            ],
        )
    };
    decode_zero(raw)?;
    let mask = result.mask;
    Ok(FileMetadata {
        returned_mask: mask,
        inode: available(mask, STATX_INO, result.inode),
        size: available(mask, STATX_SIZE, result.size),
        blocks: available(mask, STATX_BLOCKS, result.blocks),
        links: available(mask, STATX_NLINK, result.links),
        uid: available(mask, STATX_UID, result.uid),
        gid: available(mask, STATX_GID, result.gid),
        file_type: available(mask, STATX_TYPE, result.mode & S_IFMT),
        permissions: available(mask, STATX_MODE, result.mode & !S_IFMT),
        accessed: timestamp(mask, STATX_ATIME, result.accessed)?,
        created: timestamp(mask, STATX_BTIME, result.created)?,
        changed: timestamp(mask, STATX_CTIME, result.changed)?,
        modified: timestamp(mask, STATX_MTIME, result.modified)?,
    })
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct DirectoryEntry<'a> {
    pub inode: u64,
    pub next_offset: i64,
    pub kind: u8,
    pub name: &'a CStr,
}

/// Reads one batch of x86-64 `linux_dirent64` records. A successful empty batch
/// means end of directory. The filesystems define `next_offset` (a position
/// cookie) and can return `kind` 0 when no type information is available.
pub fn getdents64<'a>(
    fd: BorrowedFd<'_>,
    buffer: &'a mut [u8],
) -> Result<Vec<DirectoryEntry<'a>>, SyscallError> {
    let capacity = u32::try_from(buffer.len()).map_err(|_| {
        SyscallError::InvalidInput("directory buffer capacity exceeds Linux unsigned int")
    })?;
    let raw = unsafe {
        abi::call(
            abi::GETDENTS64,
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
    let len = decode_write(raw, buffer.len())?;
    parse_dirents(&buffer[..len]).ok_or(SyscallError::UnexpectedReturn(raw))
}

fn parse_dirents(mut bytes: &[u8]) -> Option<Vec<DirectoryEntry<'_>>> {
    let mut entries = Vec::new();
    while !bytes.is_empty() {
        let inode = u64::from_ne_bytes(bytes.get(..8)?.try_into().ok()?);
        let next_offset = i64::from_ne_bytes(bytes.get(8..16)?.try_into().ok()?);
        let length = u16::from_ne_bytes(bytes.get(16..18)?.try_into().ok()?) as usize;
        let kind = *bytes.get(18)?;
        if length <= 19 || length % 8 != 0 {
            return None;
        }
        let name = CStr::from_bytes_until_nul(bytes.get(19..length)?).ok()?;
        if name.to_bytes().is_empty() {
            return None;
        }
        entries.push(DirectoryEntry {
            inode,
            next_offset,
            kind,
            name,
        });
        bytes = &bytes[length..];
    }
    Some(entries)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn statx_preserves_known_x86_64_abi_layout() {
        use std::mem::{align_of, offset_of, size_of};
        assert_eq!(size_of::<NativeStatx>(), 256);
        assert_eq!(align_of::<NativeStatx>(), 8);
        assert_eq!(offset_of!(NativeStatx, size), 0x28);
        assert_eq!(offset_of!(NativeStatx, accessed), 0x40);
        assert_eq!(offset_of!(NativeStatx, modified), 0x70);
        assert_eq!(offset_of!(NativeStatx, extensions), 0x90);
        assert_eq!(size_of::<NativeTimestamp>(), 16);
        assert_eq!(offset_of!(NativeTimestamp, nanos), 8);
    }

    #[test]
    fn directory_parser_rejects_bad_records_and_preserves_record_order() {
        let mut record = [0_u8; 24];
        record[..8].copy_from_slice(&7_u64.to_ne_bytes());
        record[8..16].copy_from_slice(&13_i64.to_ne_bytes());
        record[16..18].copy_from_slice(&24_u16.to_ne_bytes());
        record[18] = 8;
        record[19..21].copy_from_slice(b"ok");
        assert_eq!(
            parse_dirents(&record).unwrap(),
            vec![DirectoryEntry {
                inode: 7,
                next_offset: 13,
                kind: 8,
                name: c"ok"
            }]
        );
        assert!(parse_dirents(&record[..23]).is_none());
        record[21..].fill(b'x');
        assert!(parse_dirents(&record).is_none());
    }
}
