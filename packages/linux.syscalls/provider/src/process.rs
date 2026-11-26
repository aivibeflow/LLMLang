use super::{
    abi, decode_nonnegative, decode_zero, write, LinuxFd, SyscallError, AT_EMPTY_PATH, EINTR,
};
use std::convert::Infallible;
use std::ffi::{c_char, CStr};
use std::fmt;
use std::num::NonZeroI32;
use std::os::fd::AsRawFd;
use std::ptr;

pub const WNOHANG: i32 = 1;
pub const WUNTRACED: i32 = 2;
pub const WCONTINUED: i32 = 8;

const CLONE: usize = 56;
const EXECVEAT: usize = 322;
const CLONE3: usize = 435;
const SIGCHLD: usize = 17;

/// Owns responsibility for collecting one direct child's status. Wait can be
/// retried on interruption. A terminal status consumes the live child token.
/// The caller must coordinate with other process code that reaps children.
#[must_use = "collect the child status with wait4 or waitid"]
#[derive(Debug)]
pub struct ChildPid(Option<NonZeroI32>);

impl ChildPid {
    pub fn pid(&self) -> Option<i32> {
        self.0.map(NonZeroI32::get)
    }

    pub(super) fn retire(&mut self) {
        self.0 = None;
    }
}

fn decode_pid(raw: isize) -> Result<ChildPid, SyscallError> {
    let pid = decode_nonnegative(raw)?;
    let pid = i32::try_from(pid)
        .ok()
        .and_then(NonZeroI32::new)
        .ok_or(SyscallError::UnexpectedReturn(raw))?;
    Ok(ChildPid(Some(pid)))
}

pub fn getpid() -> Result<i32, SyscallError> {
    let raw = unsafe { abi::invoke(abi::GETPID, [0; 6]) };
    decode_pid(raw).map(|pid| pid.0.expect("decode_pid always returns a live PID").get())
}

struct ExecVectors {
    args: Vec<*const c_char>,
    env: Vec<*const c_char>,
}

impl ExecVectors {
    fn new(args: &[&CStr], env: &[&CStr]) -> Result<Self, SyscallError> {
        if args.is_empty() {
            return Err(SyscallError::InvalidInput("execve requires argv[0]"));
        }
        Ok(Self {
            args: args
                .iter()
                .map(|value| value.as_ptr())
                .chain([ptr::null()])
                .collect(),
            env: env
                .iter()
                .map(|value| value.as_ptr())
                .chain([ptr::null()])
                .collect(),
        })
    }
}

/// Holds immutable arguments and both sentinel-terminated native vectors.
pub struct ExecImage<'a> {
    path: &'a CStr,
    vectors: ExecVectors,
}

impl<'a> ExecImage<'a> {
    pub fn new(path: &'a CStr, args: &[&'a CStr], env: &[&'a CStr]) -> Result<Self, SyscallError> {
        Ok(Self {
            path,
            vectors: ExecVectors::new(args, env)?,
        })
    }

    fn arguments(&self) -> [usize; 6] {
        [
            self.path.as_ptr() as usize,
            self.vectors.args.as_ptr() as usize,
            self.vectors.env.as_ptr() as usize,
            0,
            0,
            0,
        ]
    }
}

#[derive(Debug)]
pub enum ForkOutcome {
    Parent(ChildPid),
    Child,
}

/// Split execution into a parent with a child token and a child continuation.
///
/// # Safety
///
/// The child of a multi-threaded process must perform only async-signal-safe
/// actions until execve or exit. The caller must install a context where Rust
/// unwinding, allocation, runtime locks and TLS remain untouched in the child.
/// Prefer `fork_execve` for a child which simply runs an executable.
pub unsafe fn fork() -> Result<ForkOutcome, SyscallError> {
    let raw = unsafe { abi::invoke(abi::FORK, [0; 6]) };
    if raw == 0 {
        return Ok(ForkOutcome::Child);
    }
    decode_pid(raw).map(ForkOutcome::Parent)
}

/// Replaces the process image. The operation returns only on failure.
pub fn execve(image: &ExecImage<'_>) -> Result<Infallible, SyscallError> {
    let raw = unsafe { abi::invoke(abi::EXECVE, image.arguments()) };
    decode_nonnegative(raw)?;
    Err(SyscallError::UnexpectedReturn(raw))
}

/// Runs fork followed by execve in the child without allocating in the child.
/// A failed execve exits the child with code 127. The parent can distinguish
/// fork failure from a child status, but cannot distinguish a failed execve
/// from an executable that itself exits with 127.
pub fn fork_execve(image: &ExecImage<'_>) -> Result<ChildPid, SyscallError> {
    let arguments = image.arguments();
    let raw = unsafe { abi::invoke(abi::FORK, [0; 6]) };
    finish_copy_launch(raw, abi::EXECVE, arguments)
}

/// Creates a copy-on-write child that immediately exits with the given
/// status. The parent receives the child and is responsible for waiting.
pub fn fork_exit(status: i32) -> Result<ChildPid, SyscallError> {
    let raw = unsafe { abi::invoke(abi::FORK, [0; 6]) };
    if raw == 0 {
        exit_child(status);
    }
    decode_pid(raw)
}

/// Launches a SIGCHLD child through the native x86-64 clone entry. The
/// zero stack argument and absence of CLONE_VM retain the copied stack;
/// no TLS, TID pointers, namespace flags or child continuation are exposed.
pub fn clone_execve(image: &ExecImage<'_>) -> Result<ChildPid, SyscallError> {
    let arguments = image.arguments();
    let raw = unsafe { abi::invoke(CLONE, [SIGCHLD, 0, 0, 0, 0, 0]) };
    finish_copy_launch(raw, abi::EXECVE, arguments)
}

/// First published prefix of the native Linux clone_args UAPI. Missing
/// optional trailing attributes are zero-filled by the kernel.
#[derive(Default)]
#[repr(C)]
struct CloneArgsV0 {
    flags: u64,
    pidfd: u64,
    child_tid: u64,
    parent_tid: u64,
    exit_signal: u64,
    stack: u64,
    stack_size: u64,
    tls: u64,
}

const _: () = {
    assert!(std::mem::size_of::<CloneArgsV0>() == 64);
    assert!(std::mem::align_of::<CloneArgsV0>() == 8);
    assert!(std::mem::offset_of!(CloneArgsV0, exit_signal) == 32);
    assert!(std::mem::offset_of!(CloneArgsV0, tls) == 56);
};

/// Launches the same copy-on-write process profile through native clone3.
/// Availability errors (including a filtered ENOSYS) are returned to the
/// parent. This operation never substitutes another process creation entry.
pub fn clone3_execve(image: &ExecImage<'_>) -> Result<ChildPid, SyscallError> {
    let arguments = image.arguments();
    let clone = CloneArgsV0 {
        exit_signal: SIGCHLD as u64,
        ..CloneArgsV0::default()
    };
    let raw = unsafe {
        abi::invoke(
            CLONE3,
            [
                ptr::from_ref(&clone) as usize,
                std::mem::size_of::<CloneArgsV0>(),
                0,
                0,
                0,
                0,
            ],
        )
    };
    finish_copy_launch(raw, abi::EXECVE, arguments)
}

#[inline]
fn finish_copy_launch(
    raw: isize,
    exec_entry: usize,
    arguments: [usize; 6],
) -> Result<ChildPid, SyscallError> {
    if raw == 0 {
        // This path can run in a child of a multi-threaded process. Do not
        // invoke Rust allocation, cleanup, unwinding, libc or user callbacks.
        unsafe { abi::invoke(exec_entry, arguments) };
        exit_child(127);
    }
    decode_pid(raw)
}

#[inline]
fn exit_child(status: i32) -> ! {
    unsafe {
        abi::invoke(abi::EXIT, [status as usize, 0, 0, 0, 0, 0]);
        // A sandbox can deny exit. Trap without running Rust cleanup.
        std::arch::asm!("ud2", options(noreturn, nostack));
    }
}

const MFD_ALLOW_SEALING: usize = 0x0002;
const MFD_EXEC: usize = 0x0010;
const F_ADD_SEALS: usize = 1033;
const F_SEAL_SEAL: usize = 0x0001;
const F_SEAL_SHRINK: usize = 0x0002;
const F_SEAL_GROW: usize = 0x0004;
const F_SEAL_WRITE: usize = 0x0008;
const F_SEAL_EXEC: usize = 0x0020;
const EXECUTABLE_SEALS: usize =
    F_SEAL_SEAL | F_SEAL_SHRINK | F_SEAL_GROW | F_SEAL_WRITE | F_SEAL_EXEC;

/// Owns an executable CLOEXEC memfd whose bytes, size and execute bits are
/// sealed. This type does not expose an unsealed or caller-selected descriptor.
#[derive(Debug)]
pub struct SealedExecutable(LinuxFd);

/// Create an executable memfd, fill it with the supplied immutable bytes and
/// apply seals before returning. The kernel validates the format on execution.
pub fn prepare_execveat_fd(mut bytes: &[u8]) -> Result<SealedExecutable, SyscallError> {
    let fd = super::files_extra2::memfd_create_with_flags(
        c"llmlang-execveat",
        MFD_ALLOW_SEALING | MFD_EXEC,
    )?;
    while !bytes.is_empty() {
        match write(fd.borrow(), bytes) {
            Ok(0) => return Err(SyscallError::UnexpectedReturn(0)),
            Ok(progress) => bytes = &bytes[progress..],
            Err(error) if error.is_errno(EINTR) => continue,
            Err(error) => return Err(error),
        }
    }
    let raw = unsafe {
        abi::invoke(
            abi::FCNTL,
            [
                fd.as_raw_fd() as usize,
                F_ADD_SEALS,
                EXECUTABLE_SEALS,
                0,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)?;
    Ok(SealedExecutable(fd))
}

/// Immutable, sentinel-terminated argument vectors for one sealed descriptor.
pub struct ExecveAtImage<'a> {
    executable: &'a SealedExecutable,
    vectors: ExecVectors,
}

impl<'a> ExecveAtImage<'a> {
    pub fn new(
        executable: &'a SealedExecutable,
        args: &[&'a CStr],
        env: &[&'a CStr],
    ) -> Result<Self, SyscallError> {
        Ok(Self {
            executable,
            vectors: ExecVectors::new(args, env)?,
        })
    }

    fn arguments(&self) -> [usize; 6] {
        [
            self.executable.0.as_raw_fd() as usize,
            c"".as_ptr() as usize,
            self.vectors.args.as_ptr() as usize,
            self.vectors.env.as_ptr() as usize,
            AT_EMPTY_PATH as usize,
            0,
        ]
    }
}

/// Replaces the process image using only a prepared descriptor and
/// AT_EMPTY_PATH. Failures return the native errno.
pub fn execveat(image: &ExecveAtImage<'_>) -> Result<Infallible, SyscallError> {
    let raw = unsafe { abi::invoke(EXECVEAT, image.arguments()) };
    decode_nonnegative(raw)?;
    Err(SyscallError::UnexpectedReturn(raw))
}

/// Runs the prepared descriptor in a fork child. A failed execveat exits
/// with 127, with the same status ambiguity as fork_execve.
pub fn fork_execveat(image: &ExecveAtImage<'_>) -> Result<ChildPid, SyscallError> {
    let arguments = image.arguments();
    let raw = unsafe { abi::invoke(abi::FORK, [0; 6]) };
    finish_copy_launch(raw, EXECVEAT, arguments)
}

#[derive(Debug)]
pub enum VforkExecError {
    MaskSetup(SyscallError),
    Launch(SyscallError),
    MaskRestore {
        error: SyscallError,
        launch: Result<ChildPid, SyscallError>,
    },
}

impl fmt::Display for VforkExecError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::MaskSetup(error) => write!(formatter, "set vfork signal mask: {error}"),
            Self::Launch(error) => write!(formatter, "launch vfork child: {error}"),
            Self::MaskRestore { error, .. } => {
                write!(formatter, "restore vfork signal mask: {error}")
            }
        }
    }
}

impl std::error::Error for VforkExecError {}

/// Start a vfork child through a stackless x86-64 assembly continuation.
/// The calling thread first blocks every blockable signal, so no child
/// signal handler can run on its shared stack before execve. The next
/// program inherits that mask. The parent restores its own prior mask.
/// If restoration fails, the error retains either the live child token
/// or the syscall's launch error. Failed child execve exits with 127.
pub fn vfork_execve_masked(image: &ExecImage<'_>) -> Result<ChildPid, VforkExecError> {
    let arguments = image.arguments();
    let mut previous_mask = 0_u64;
    super::signal_fd::replace_mask(u64::MAX, Some(&mut previous_mask))
        .map_err(VforkExecError::MaskSetup)?;

    let raw = unsafe { abi::vfork_exec(arguments) };

    let restore = super::signal_fd::replace_mask(previous_mask, None);
    let launch = decode_pid(raw);
    if let Err(error) = restore {
        return Err(VforkExecError::MaskRestore { error, launch });
    }
    launch.map_err(VforkExecError::Launch)
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct WaitStatus(i32);

impl WaitStatus {
    pub fn raw(self) -> i32 {
        self.0
    }

    pub fn exited(self) -> Option<u8> {
        (self.0 & 0x7f == 0).then_some(((self.0 >> 8) & 0xff) as u8)
    }

    pub fn signal(self) -> Option<u8> {
        let signal = (self.0 & 0x7f) as u8;
        (signal != 0 && signal != 0x7f).then_some(signal)
    }

    pub fn stopped(self) -> Option<u8> {
        (self.0 & 0xff == 0x7f).then_some(((self.0 >> 8) & 0xff) as u8)
    }

    pub fn continued(self) -> bool {
        self.0 == 0xffff
    }
}

/// Waits for an owned child, returning None only when WNOHANG finds no status.
/// This profile does not request the optional rusage output.
pub fn wait4(child: &mut ChildPid, options: i32) -> Result<Option<WaitStatus>, SyscallError> {
    let pid = child
        .pid()
        .ok_or(SyscallError::InvalidInput("child has already been reaped"))?;
    let mut status = 0_i32;
    let raw = unsafe {
        abi::invoke(
            abi::WAIT4,
            [
                pid as usize,
                (&mut status as *mut i32) as usize,
                options as usize,
                0,
                0,
                0,
            ],
        )
    };
    match decode_nonnegative(raw)? {
        0 if options & WNOHANG != 0 => Ok(None),
        result if result == pid as usize => {
            let status = WaitStatus(status);
            if status.exited().is_some() || status.signal().is_some() {
                child.retire();
            }
            Ok(Some(status))
        }
        _ => Err(SyscallError::UnexpectedReturn(raw)),
    }
}

#[cfg(test)]
mod descriptor_tests {
    use super::*;

    #[test]
    fn prepared_execveat_descriptor_enforces_immutable_bytes_and_exec() {
        const F_GET_SEALS: usize = 1034;
        let executable = prepare_execveat_fd(b"fixed").unwrap();
        let fd = executable.0.borrow();
        let raw = unsafe {
            abi::invoke(
                abi::FCNTL,
                [fd.as_raw_fd() as usize, F_GET_SEALS, 0, 0, 0, 0],
            )
        };
        assert_eq!(
            decode_nonnegative(raw).unwrap() & EXECUTABLE_SEALS,
            EXECUTABLE_SEALS
        );
        assert_eq!(super::super::fcntl_getfd(fd).unwrap() & 1, 1);
        assert!(write(fd, b"change").unwrap_err().is_errno(1));
        assert!(super::super::ftruncate(fd, 0).unwrap_err().is_errno(1));
        assert!(super::super::fchmod(fd, 0o600).unwrap_err().is_errno(1));
    }
}
