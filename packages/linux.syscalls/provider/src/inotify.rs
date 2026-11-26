use super::{
    abi, decode_nonnegative, decode_zero, read, LinuxFd, ReadOutcome, SyscallError, O_CLOEXEC,
    O_NONBLOCK,
};
use std::cell::{Cell, RefCell};
use std::collections::BTreeMap;
use std::ffi::CStr;
use std::os::fd::{AsFd, AsRawFd, BorrowedFd};

const INOTIFY_INIT: usize = 253;
const INOTIFY_ADD_WATCH: usize = 254;
const INOTIFY_RM_WATCH: usize = 255;
const INOTIFY_INIT1: usize = 294;
const IN_MASK_CREATE: usize = 0x1000_0000;
const EVENT_HEADER_LEN: usize = 16;
pub const IN_Q_OVERFLOW: u32 = 0x0000_4000;
pub const IN_IGNORED: u32 = 0x0000_8000;
pub const IN_ISDIR: u32 = 0x4000_0000;

/// Owns an inotify instance. Watch lifetimes keep it alive. Records in its
/// queue can outlive the watch that originally generated them.
#[derive(Debug)]
pub struct Inotify {
    fd: LinuxFd,
    generation: Cell<u64>,
    watches: RefCell<BTreeMap<i32, u64>>,
}

impl Inotify {
    fn new(raw: isize) -> Result<Self, SyscallError> {
        Ok(Self {
            fd: LinuxFd::from_result(raw)?,
            generation: Cell::new(0),
            watches: RefCell::new(BTreeMap::new()),
        })
    }

    pub fn borrow(&self) -> BorrowedFd<'_> {
        self.fd.borrow()
    }

    pub fn into_fd(self) -> LinuxFd {
        self.fd
    }
}

impl AsFd for Inotify {
    fn as_fd(&self) -> BorrowedFd<'_> {
        self.borrow()
    }
}

#[repr(i32)]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum InotifyMode {
    Blocking = 0,
    NonBlocking = O_NONBLOCK,
}

/// Opens the legacy blocking instance; Linux leaves CLOEXEC clear.
pub fn inotify_init() -> Result<Inotify, SyscallError> {
    Inotify::new(unsafe { abi::invoke(INOTIFY_INIT, [0; 6]) })
}

/// Opens a blocking or nonblocking instance, always with atomic CLOEXEC.
pub fn inotify_init1(mode: InotifyMode) -> Result<Inotify, SyscallError> {
    Inotify::new(unsafe {
        abi::invoke(
            INOTIFY_INIT1,
            [(O_CLOEXEC | mode as i32) as usize, 0, 0, 0, 0, 0],
        )
    })
}

/// Event selection for a newly owned watch. The kernel may also report
/// lifecycle and overflow events outside the watch's requested mask.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct WatchMask(u32);

impl WatchMask {
    pub const ACCESS: Self = Self(0x0000_0001);
    pub const MODIFY: Self = Self(0x0000_0002);
    pub const ATTRIB: Self = Self(0x0000_0004);
    pub const CLOSE_WRITE: Self = Self(0x0000_0008);
    pub const CLOSE_NOWRITE: Self = Self(0x0000_0010);
    pub const OPEN: Self = Self(0x0000_0020);
    pub const MOVED_FROM: Self = Self(0x0000_0040);
    pub const MOVED_TO: Self = Self(0x0000_0080);
    pub const CREATE: Self = Self(0x0000_0100);
    pub const DELETE: Self = Self(0x0000_0200);
    pub const DELETE_SELF: Self = Self(0x0000_0400);
    pub const MOVE_SELF: Self = Self(0x0000_0800);

    pub const fn combine(self, other: Self) -> Self {
        Self(self.0 | other.0)
    }

    pub const fn bits(self) -> u32 {
        self.0
    }
}

/// Owns one watch within the borrowed instance. Dropping the token attempts
/// removal once. Use `inotify_rm_watch` to observe the operation's result.
#[derive(Debug)]
pub struct InotifyWatch<'a> {
    instance: &'a Inotify,
    descriptor: i32,
    generation: u64,
    live: bool,
}

impl InotifyWatch<'_> {
    pub fn descriptor(&self) -> i32 {
        self.descriptor
    }

    fn remove(&mut self) -> Result<(), SyscallError> {
        if !self.live {
            return Ok(());
        }
        self.live = false;
        let mut watches = self.instance.watches.borrow_mut();
        if watches.get(&self.descriptor) != Some(&self.generation) {
            return Err(SyscallError::InvalidInput(
                "inotify watch descriptor has been superseded",
            ));
        }
        watches.remove(&self.descriptor);
        drop(watches);
        decode_zero(unsafe {
            abi::invoke(
                INOTIFY_RM_WATCH,
                [
                    self.instance.borrow().as_raw_fd() as usize,
                    self.descriptor as usize,
                    0,
                    0,
                    0,
                    0,
                ],
            )
        })
    }
}

impl Drop for InotifyWatch<'_> {
    fn drop(&mut self) {
        let _ = self.remove();
    }
}

/// Adds a new watch for the object reached by following the pathname. The
/// atomic IN_MASK_CREATE flag rejects an existing watch for that same object.
pub fn inotify_add_watch<'a>(
    instance: &'a Inotify,
    path: &CStr,
    mask: WatchMask,
) -> Result<InotifyWatch<'a>, SyscallError> {
    let generation = instance
        .generation
        .get()
        .checked_add(1)
        .ok_or(SyscallError::InvalidInput(
            "inotify watch generations exhausted",
        ))?;
    let raw = unsafe {
        abi::invoke(
            INOTIFY_ADD_WATCH,
            [
                instance.borrow().as_raw_fd() as usize,
                path.as_ptr() as usize,
                IN_MASK_CREATE | mask.0 as usize,
                0,
                0,
                0,
            ],
        )
    };
    let descriptor = decode_nonnegative(raw)?;
    let descriptor = i32::try_from(descriptor).map_err(|_| SyscallError::UnexpectedReturn(raw))?;
    instance.generation.set(generation);
    instance.watches.borrow_mut().insert(descriptor, generation);
    Ok(InotifyWatch {
        instance,
        descriptor,
        generation,
        live: true,
    })
}

/// Consumes the token and removes the exact active watch. Linux can return
/// EINVAL if the watch was already removed automatically.
pub fn inotify_rm_watch(mut watch: InotifyWatch<'_>) -> Result<(), SyscallError> {
    watch.remove()
}

/// One record from the kernel's event queue. A descriptor of -1 may indicate
/// queue overflow. File names are raw NUL-terminated bytes without padding.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct InotifyEvent<'a> {
    pub descriptor: i32,
    pub mask: u32,
    pub cookie: u32,
    pub name: Option<&'a CStr>,
}

/// Reads and decodes one bounded batch of inotify records. A nonblocking
/// instance can report EAGAIN; an undersized buffer can report EINVAL.
pub fn read_inotify_events<'a>(
    instance: &Inotify,
    buffer: &'a mut [u8],
) -> Result<Vec<InotifyEvent<'a>>, SyscallError> {
    let bytes = match read(instance.borrow(), buffer)? {
        ReadOutcome::Progress(bytes) => bytes,
        ReadOutcome::Eof => 0,
    };
    decode_events(&buffer[..bytes]).ok_or(SyscallError::UnexpectedReturn(bytes as isize))
}

fn decode_events(mut bytes: &[u8]) -> Option<Vec<InotifyEvent<'_>>> {
    let mut events = Vec::new();
    while !bytes.is_empty() {
        let (header, rest) = bytes.split_at_checked(EVENT_HEADER_LEN)?;
        let descriptor = i32::from_ne_bytes(header[..4].try_into().ok()?);
        let mask = u32::from_ne_bytes(header[4..8].try_into().ok()?);
        let cookie = u32::from_ne_bytes(header[8..12].try_into().ok()?);
        let name_len = u32::from_ne_bytes(header[12..16].try_into().ok()?) as usize;
        if name_len % EVENT_HEADER_LEN != 0 {
            return None;
        }
        let (name, remaining) = rest.split_at_checked(name_len)?;
        let name = if name.is_empty() {
            None
        } else {
            let name = CStr::from_bytes_until_nul(name).ok()?;
            if name.to_bytes().is_empty() {
                return None;
            }
            Some(name)
        };
        events.push(InotifyEvent {
            descriptor,
            mask,
            cookie,
            name,
        });
        bytes = remaining;
    }
    Some(events)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn event_decoder_preserves_overflow_and_rejects_malformed_records() {
        let mut raw = [0_u8; 32];
        raw[..4].copy_from_slice(&(-1_i32).to_ne_bytes());
        raw[4..8].copy_from_slice(&IN_Q_OVERFLOW.to_ne_bytes());
        let expected = InotifyEvent {
            descriptor: -1,
            mask: IN_Q_OVERFLOW,
            cookie: 0,
            name: None,
        };
        assert_eq!(decode_events(&raw[..16]).unwrap(), [expected]);
        assert!(decode_events(&raw[..15]).is_none());
        raw[12..16].copy_from_slice(&16_u32.to_ne_bytes());
        assert!(decode_events(&raw[..31]).is_none());
        assert!(decode_events(&raw).is_none());
        raw[16..].fill(b'x');
        assert!(decode_events(&raw).is_none());
        raw[17] = 0;
        assert_eq!(decode_events(&raw).unwrap()[0].name, Some(c"x"));
    }
}
