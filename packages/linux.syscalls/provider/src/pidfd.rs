use super::{
    abi, decode_nonnegative, decode_write, decode_zero, getpid, ChildPid, LinuxFd, Mapping,
    SyscallError,
};
use std::fmt;
use std::os::fd::{AsRawFd, BorrowedFd};

const PIDFD_SEND_SIGNAL: usize = 424;
const PIDFD_OPEN: usize = 434;
const PIDFD_GETFD: usize = 438;
const PROCESS_MADVISE: usize = 440;
const PROCESS_MRELEASE: usize = 448;
const KCMP: usize = 312;
const KCMP_FILE: usize = 0;

/// Owns a close-on-exec descriptor for the child selected by `pidfd_open`.
/// The descriptor pins that identity until drop closes it.
#[derive(Debug)]
pub struct ChildPidFd(LinuxFd);

/// Opens a descriptor for a child still held by its wait token. The caller
/// must exclude independent reaping and automatic SIGCHLD reaping between
/// child creation and the call, so the numeric ID cannot already be reused.
pub fn pidfd_open(child: &ChildPid) -> Result<ChildPidFd, SyscallError> {
    let pid = child
        .pid()
        .ok_or(SyscallError::InvalidInput("child has already been reaped"))?;
    open_pidfd(pid).map(ChildPidFd)
}

fn open_pidfd(pid: i32) -> Result<LinuxFd, SyscallError> {
    let raw = unsafe { abi::invoke(PIDFD_OPEN, [pid as usize, 0, 0, 0, 0, 0]) };
    LinuxFd::from_result(raw)
}

/// The child control profile exposes a permission/existence check and TERM.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ChildSignal {
    Check = 0,
    Terminate = 15,
}

/// Checks or sends TERM to the original child identity. A successful TERM
/// request does not establish child termination. Collect status with wait4.
pub fn pidfd_send_signal(target: &ChildPidFd, signal: ChildSignal) -> Result<(), SyscallError> {
    let raw = unsafe {
        abi::invoke(
            PIDFD_SEND_SIGNAL,
            [target.0.as_raw_fd() as usize, signal as usize, 0, 0, 0, 0],
        )
    };
    decode_zero(raw)
}

/// Compare two borrowed descriptors in the calling process. Only equality
/// of their open file descriptions is exposed, with no ordering or target PID.
pub fn kcmp(left: BorrowedFd<'_>, right: BorrowedFd<'_>) -> Result<bool, SyscallError> {
    let pid = getpid()? as usize;
    let raw = unsafe {
        abi::invoke(
            KCMP,
            [
                pid,
                pid,
                KCMP_FILE,
                left.as_raw_fd() as usize,
                right.as_raw_fd() as usize,
                0,
            ],
        )
    };
    match decode_nonnegative(raw)? {
        0 => Ok(true),
        1 | 2 => Ok(false),
        _ => Err(SyscallError::UnexpectedReturn(raw)),
    }
}

/// Binds a child descriptor slot to the same-numbered descriptor borrowed
/// from the current process. Child code may have changed that slot, so the
/// duplicate is checked for open file description equality before release.
#[derive(Debug)]
pub struct KnownChildDescriptor<'a> {
    child: &'a ChildPidFd,
    expected: BorrowedFd<'a>,
}

impl<'a> KnownChildDescriptor<'a> {
    pub fn new(child: &'a ChildPidFd, expected: BorrowedFd<'a>) -> Self {
        Self { child, expected }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ChildDescriptorError {
    Duplicate(SyscallError),
    Compare(SyscallError),
    DifferentDescription,
}

impl fmt::Display for ChildDescriptorError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Duplicate(error) => {
                write!(formatter, "duplicate recorded child descriptor: {error}")
            }
            Self::Compare(error) => {
                write!(formatter, "compare duplicated child descriptor: {error}")
            }
            Self::DifferentDescription => {
                formatter.write_str("child descriptor refers to a different open file description")
            }
        }
    }
}

impl std::error::Error for ChildDescriptorError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Duplicate(error) | Self::Compare(error) => Some(error),
            Self::DifferentDescription => None,
        }
    }
}

/// Duplicate only the recorded own-child slot, with flags zero. The
/// kernel sets CLOEXEC. The candidate is dropped on a comparison failure
/// or an open file description mismatch.
pub fn pidfd_getfd(known: &KnownChildDescriptor<'_>) -> Result<LinuxFd, ChildDescriptorError> {
    let raw = unsafe {
        abi::invoke(
            PIDFD_GETFD,
            [
                known.child.0.as_raw_fd() as usize,
                known.expected.as_raw_fd() as usize,
                0,
                0,
                0,
                0,
            ],
        )
    };
    let candidate = LinuxFd::from_result(raw).map_err(ChildDescriptorError::Duplicate)?;
    if kcmp(known.expected, candidate.borrow()).map_err(ChildDescriptorError::Compare)? {
        Ok(candidate)
    } else {
        Err(ChildDescriptorError::DifferentDescription)
    }
}

/// Non-destructive advice supported for an owned local anonymous mapping.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ProcessAdvice {
    WillNeed = 3,
    Cold = 20,
}

#[repr(C)]
struct AdviceVector {
    address: usize,
    length: usize,
}

const _: () = {
    assert!(std::mem::size_of::<AdviceVector>() == 16);
    assert!(std::mem::align_of::<AdviceVector>() == 8);
    assert!(std::mem::offset_of!(AdviceVector, length) == 8);
};

/// Apply one advisory hint to the owned range through a pidfd for this process.
/// Counts reflect native byte progress, bounded by the mapping's requested
/// length. The hint can affect residency without changing bytes or protections.
pub fn process_madvise(
    mapping: &mut Mapping,
    advice: ProcessAdvice,
) -> Result<usize, SyscallError> {
    let bytes = mapping.as_slice();
    if bytes.is_empty() {
        return Err(SyscallError::InvalidInput("mapping has no live range"));
    }
    let target = open_pidfd(getpid()?)?;
    let vector = AdviceVector {
        address: bytes.as_ptr() as usize,
        length: bytes.len(),
    };
    // The exclusive mapping borrow keeps the complete native range owned,
    // excludes permission changes and excludes live caller slices. The
    // kernel retains neither this vector nor the self pidfd.
    let raw = unsafe {
        abi::invoke(
            PROCESS_MADVISE,
            [
                target.as_raw_fd() as usize,
                std::ptr::from_ref(&vector) as usize,
                1,
                advice as usize,
                0,
                0,
            ],
        )
    };
    decode_write(raw, vector.length)
}

/// Ask Linux to release memory for a tracked child which is already
/// exiting. The kernel checks eligibility and returns the native error
/// when the child still runs or has already released its address space.
/// Keep the child's wait token to collect its exit status separately.
pub fn process_mrelease(target: &ChildPidFd) -> Result<(), SyscallError> {
    // The owned pidfd pins the original direct-child identity. The kernel
    // checks its exit state atomically with obtaining the address space.
    let raw = unsafe {
        abi::invoke(
            PROCESS_MRELEASE,
            [target.0.as_raw_fd() as usize, 0, 0, 0, 0, 0],
        )
    };
    decode_zero(raw)
}
