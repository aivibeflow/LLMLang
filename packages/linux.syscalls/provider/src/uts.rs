use std::cell::Cell;
use std::fmt;
use std::marker::PhantomData;
use std::os::fd::{AsFd, AsRawFd};
use std::rc::Rc;

use super::mounts::detached_proc_mount;
use super::{abi, decode_zero, openat, Directory, LinuxFd, OpenOptions, SyscallError, O_CLOEXEC, O_RDONLY};

const SETHOSTNAME: usize = 170;
const SETDOMAINNAME: usize = 171;
pub(super) const UNSHARE: usize = 272;
const SETNS: usize = 308;
const CLONE_NEWUTS: usize = 0x0400_0000;
const HOSTNAME_MAX: usize = 64;

thread_local! {
    static GENERATION: Cell<u64> = const { Cell::new(0) };
}

/// Thread-affine authority to update the current private UTS namespace.
/// A subsequent provider namespace switch invalidates this authority.
#[derive(Debug)]
pub struct UtsNamespace {
    generation: u64,
    thread_affine: PhantomData<Rc<()>>,
}

impl UtsNamespace {
    fn check_current(&self) -> Result<(), SyscallError> {
        if self.generation == GENERATION.get() {
            Ok(())
        } else {
            Err(SyscallError::InvalidInput("stale UTS namespace authority"))
        }
    }
}

fn enter_uts(number: usize, arguments: [usize; 6]) -> Result<UtsNamespace, SyscallError> {
    let generation = GENERATION
        .get()
        .checked_add(1)
        .ok_or(SyscallError::InvalidInput(
            "UTS namespace generation exhausted",
        ))?;
    decode_zero(unsafe { abi::invoke(number, arguments) })?;
    GENERATION.set(generation);
    Ok(UtsNamespace {
        generation,
        thread_affine: PhantomData,
    })
}

/// Copy the caller's UTS namespace and enter it with a new provider authority.
/// Linux requires the applicable capability.
pub fn unshare_uts() -> Result<UtsNamespace, SyscallError> {
    enter_uts(UNSHARE, [CLONE_NEWUTS, 0, 0, 0, 0, 0])
}

/// Assign the hostname in the private UTS namespace. Callers that use an
/// external namespace API must keep this thread in a private UTS namespace
/// for the token's lifetime.
pub fn sethostname(namespace: &UtsNamespace, name: &[u8]) -> Result<(), SyscallError> {
    namespace.check_current()?;
    if name.len() > HOSTNAME_MAX {
        return Err(SyscallError::InvalidInput("hostname exceeds 64 bytes"));
    }
    // Linux reads exactly name.len() bytes, including embedded NUL bytes.
    decode_zero(unsafe {
        abi::invoke(
            SETHOSTNAME,
            [name.as_ptr() as usize, name.len(), 0, 0, 0, 0],
        )
    })
}

/// Assign the NIS domain name in the current private UTS namespace.
pub fn setdomainname(namespace: &UtsNamespace, name: &[u8]) -> Result<(), SyscallError> {
    namespace.check_current()?;
    if name.len() > HOSTNAME_MAX {
        return Err(SyscallError::InvalidInput("domain name exceeds 64 bytes"));
    }
    decode_zero(unsafe {
        abi::invoke(
            SETDOMAINNAME,
            [name.as_ptr() as usize, name.len(), 0, 0, 0, 0],
        )
    })
}

/// Keeps an exact provider-created private UTS namespace alive on this thread.
#[derive(Debug)]
pub struct SavedUtsNamespace {
    descriptor: LinuxFd,
    thread_affine: PhantomData<Rc<()>>,
}

#[derive(Debug)]
pub enum PinUtsError {
    OpenProc(SyscallError),
    Unshare(SyscallError),
    Capture {
        namespace: UtsNamespace,
        error: SyscallError,
    },
}

impl fmt::Display for PinUtsError {
    fn fmt(&self, output: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::OpenProc(error) => write!(output, "cannot prepare detached procfs: {error}"),
            Self::Unshare(error) => write!(output, "cannot enter new UTS namespace: {error}"),
            Self::Capture { error, .. } => write!(
                output,
                "entered new UTS namespace, but could not pin it: {error}"
            ),
        }
    }
}

impl std::error::Error for PinUtsError {}

/// Enter a fresh private UTS namespace and retain its exact descriptor.
/// The kernel lookup starts at a detached procfs. A capture failure returns
/// the live authority for the namespace already entered by this thread.
pub fn unshare_uts_pinned() -> Result<(UtsNamespace, SavedUtsNamespace), PinUtsError> {
    let proc_root = detached_proc_mount().map_err(PinUtsError::OpenProc)?;
    let namespace = unshare_uts().map_err(PinUtsError::Unshare)?;
    match openat(
        Directory::Borrowed(proc_root.as_fd()),
        c"thread-self/ns/uts",
        OpenOptions {
            flags: O_RDONLY | O_CLOEXEC,
            mode: 0,
        },
    ) {
        Ok(descriptor) => Ok((
            namespace,
            SavedUtsNamespace {
                descriptor,
                thread_affine: PhantomData,
            },
        )),
        Err(error) => Err(PinUtsError::Capture { namespace, error }),
    }
}

/// Join exactly the provider-created UTS namespace pinned by this thread.
/// The caller must coordinate any external namespace changes with this API.
pub fn setns_uts(target: &SavedUtsNamespace) -> Result<UtsNamespace, SyscallError> {
    enter_uts(
        SETNS,
        [
            target.descriptor.as_raw_fd() as usize,
            CLONE_NEWUTS,
            0,
            0,
            0,
            0,
        ],
    )
}
