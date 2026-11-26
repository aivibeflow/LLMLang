//! Scoped vhangup on a controlling terminal created by this operation.

use super::mounts::detached_devpts_mount;
use super::{abi, decode_zero, openat, setsid, Directory, LinuxFd, OpenOptions, SyscallError};
use super::{O_CLOEXEC, O_RDWR};
use std::fmt;
use std::os::fd::{AsFd, AsRawFd};

const VHANGUP: usize = 153;
const O_NOCTTY: i32 = 0o400;
const TIOCSCTTY: usize = 0x540e;
const TIOCSPTLCK: usize = 0x4004_5431;
const TIOCGPTPEER: usize = 0x5441;

/// The two owned endpoints of the new session's private pseudo-terminal.
#[derive(Debug)]
pub struct PrivatePty {
    pub session: i32,
    pub master: LinuxFd,
    pub slave: LinuxFd,
}

#[derive(Debug)]
pub enum PtyHangupError {
    OpenDevpts(SyscallError),
    OpenMaster(SyscallError),
    UnlockSlave(SyscallError),
    OpenSlave(SyscallError),
    StartSession(SyscallError),
    AttachControlling {
        session: i32,
        error: SyscallError,
    },
    Hangup {
        pty: PrivatePty,
        error: SyscallError,
    },
}

impl fmt::Display for PtyHangupError {
    fn fmt(&self, output: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::OpenDevpts(error) => write!(output, "cannot create detached devpts: {error}"),
            Self::OpenMaster(error) => write!(output, "cannot open private PTY master: {error}"),
            Self::UnlockSlave(error) => write!(output, "cannot unlock private PTY slave: {error}"),
            Self::OpenSlave(error) => write!(output, "cannot open private PTY slave: {error}"),
            Self::StartSession(error) => write!(output, "cannot start fresh session: {error}"),
            Self::AttachControlling { session, error } => {
                write!(
                    output,
                    "session {session} was created. Terminal attachment failed: {error}"
                )
            }
            Self::Hangup { pty, error } => {
                write!(
                    output,
                    "session {} acquired a private terminal. Hangup failed: {error}",
                    pty.session
                )
            }
        }
    }
}

impl std::error::Error for PtyHangupError {}

/// Open a fresh private PTY, start a new session and hang up its controlling tty.
/// The caller coordinates job control and its handling of SIGHUP and SIGCONT.
/// Linux checks the native mount and hangup capabilities. Both descriptors
/// remain owned after a successful hangup or an error from that native call.
pub fn vhangup_private_pty() -> Result<PrivatePty, PtyHangupError> {
    let devpts = detached_devpts_mount().map_err(PtyHangupError::OpenDevpts)?;
    let master = openat(
        Directory::Borrowed(devpts.as_fd()),
        c"ptmx",
        OpenOptions {
            flags: O_RDWR | O_NOCTTY,
            mode: 0,
        },
    )
    .map_err(PtyHangupError::OpenMaster)?;
    let unlocked = 0_i32;
    let raw = unsafe {
        abi::call(
            abi::IOCTL,
            [
                master.as_raw_fd() as usize,
                TIOCSPTLCK,
                std::ptr::from_ref(&unlocked) as usize,
                0,
                0,
                0,
            ],
        )
    };
    decode_zero(raw).map_err(PtyHangupError::UnlockSlave)?;
    let slave = LinuxFd::from_result(unsafe {
        abi::call(
            abi::IOCTL,
            [
                master.as_raw_fd() as usize,
                TIOCGPTPEER,
                (O_RDWR | O_NOCTTY | O_CLOEXEC) as usize,
                0,
                0,
                0,
            ],
        )
    })
    .map_err(PtyHangupError::OpenSlave)?;

    let session = setsid().map_err(PtyHangupError::StartSession)?;
    decode_zero(unsafe {
        abi::call(
            abi::IOCTL,
            [slave.as_raw_fd() as usize, TIOCSCTTY, 0, 0, 0, 0],
        )
    })
    .map_err(|error| PtyHangupError::AttachControlling { session, error })?;

    let pty = PrivatePty {
        session,
        master,
        slave,
    };
    match decode_zero(unsafe { abi::call(VHANGUP, [0; 6]) }) {
        Ok(()) => Ok(pty),
        Err(error) => Err(PtyHangupError::Hangup { pty, error }),
    }
}
