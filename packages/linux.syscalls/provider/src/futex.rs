//! Private futex waits and wakes on a borrowed native atomic word.
use std::fmt;
use std::mem::{align_of, offset_of, size_of};
use std::sync::atomic::{AtomicU32, Ordering};

use crate::{abi, decode_nonnegative, decode_zero, SyscallError, Timespec, CLOCK_MONOTONIC};

const FUTEX: usize = 202;
const SET_ROBUST_LIST: usize = 273;
const GET_ROBUST_LIST: usize = 274;
const FUTEX_WAITV: usize = 449;
const FUTEX_WAKE: usize = 454;
const FUTEX_WAIT: usize = 455;
const FUTEX_REQUEUE: usize = 456;
const WAIT_PRIVATE: usize = 128;
const WAKE_PRIVATE: usize = 129;
const FUTEX2_PRIVATE_U32: usize = 0x82;
const MATCH_ANY: usize = u32::MAX as usize;
const MAX_WAITERS: usize = 128;
const ROBUST_LIST_HEAD_BYTES: usize = 24;

/// An aligned 32-bit word for synchronization between threads of this process.
#[repr(transparent)]
#[derive(Debug)]
pub struct FutexWord(AtomicU32);

impl FutexWord {
    pub const fn new(value: u32) -> Self {
        Self(AtomicU32::new(value))
    }

    pub fn load(&self) -> u32 {
        self.0.load(Ordering::Acquire)
    }

    pub fn store(&self, value: u32) {
        self.0.store(value, Ordering::Release);
    }

    fn address(&self) -> usize {
        self.0.as_ptr() as usize
    }
}

const _: () = {
    assert!(size_of::<FutexWord>() == 4);
    assert!(align_of::<FutexWord>() == 4);
    assert!(size_of::<Timespec>() == 16);
    assert!(align_of::<Timespec>() == 8);
};

fn timeout_pointer(time: Option<&Timespec>) -> Result<usize, SyscallError> {
    match time {
        Some(time) if time.seconds() < 0 => {
            Err(SyscallError::InvalidInput("negative futex timeout"))
        }
        Some(time) => Ok(std::ptr::from_ref(time) as usize),
        None => Ok(0),
    }
}

fn wake_count(maximum: u32) -> Result<usize, SyscallError> {
    match maximum {
        1..=0x7fff_ffff => Ok(maximum as usize),
        _ => Err(SyscallError::InvalidInput(
            "futex wake count must be between 1 and i32::MAX",
        )),
    }
}

fn woken(raw: isize, maximum: usize) -> Result<u32, SyscallError> {
    let count = decode_nonnegative(raw)?;
    if count <= maximum {
        Ok(count as u32)
    } else {
        Err(SyscallError::UnexpectedReturn(raw))
    }
}

/// Wait if the word currently equals `expected`. The timeout is relative.
/// Recheck the synchronization predicate after a wake.
pub fn futex_wait_private(
    word: &FutexWord,
    expected: u32,
    timeout: Option<Timespec>,
) -> Result<(), SyscallError> {
    let pointer = timeout_pointer(timeout.as_ref())?;
    // The borrow and optional timespec remain live for the synchronous call.
    // Linux compares the word atomically and does not write it.
    let raw = unsafe {
        abi::call(
            FUTEX,
            [
                word.address(),
                WAIT_PRIVATE,
                expected as usize,
                pointer,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)
}

/// Wake up to `maximum` private waiters and expose the kernel's wake count.
pub fn futex_wake_private(word: &FutexWord, maximum: u32) -> Result<u32, SyscallError> {
    let maximum = wake_count(maximum)?;
    // The aligned word remains borrowed and the kernel uses its address as a key.
    let raw = unsafe { abi::call(FUTEX, [word.address(), WAKE_PRIVATE, maximum, 0, 0, 0]) };
    woken(raw, maximum)
}

/// Wait on a private U32 word with an optional absolute CLOCK_MONOTONIC deadline.
pub fn futex_wait(
    word: &FutexWord,
    expected: u32,
    deadline: Option<Timespec>,
) -> Result<(), SyscallError> {
    let pointer = timeout_pointer(deadline.as_ref())?;
    // The timeout is a native timespec and MATCH_ANY selects every waiter class.
    let raw = unsafe {
        abi::call(
            FUTEX_WAIT,
            [
                word.address(),
                expected as usize,
                MATCH_ANY,
                FUTEX2_PRIVATE_U32,
                pointer,
                CLOCK_MONOTONIC as usize,
            ],
        )
    };
    decode_zero(raw)
}

/// Wake up to `maximum` private U32 waiters using the native futex2 syscall.
pub fn futex_wake(word: &FutexWord, maximum: u32) -> Result<u32, SyscallError> {
    let maximum = wake_count(maximum)?;
    // The kernel uses this borrowed address as a key and does not write the word.
    let raw = unsafe {
        abi::call(
            FUTEX_WAKE,
            [word.address(), MATCH_ANY, maximum, FUTEX2_PRIVATE_U32, 0, 0],
        )
    };
    woken(raw, maximum)
}

/// A borrowed private word and its expected value for a vector wait.
#[derive(Clone, Copy, Debug)]
pub struct FutexWaiter<'a> {
    word: &'a FutexWord,
    expected: u32,
}

impl<'a> FutexWaiter<'a> {
    pub const fn new(word: &'a FutexWord, expected: u32) -> Self {
        Self { word, expected }
    }
}

#[repr(C)]
struct NativeFutexWaiter {
    expected: u64,
    address: u64,
    flags: u32,
    reserved: u32,
}

const _: () = {
    assert!(size_of::<NativeFutexWaiter>() == 24);
    assert!(align_of::<NativeFutexWaiter>() == 8);
    assert!(offset_of!(NativeFutexWaiter, address) == 8);
    assert!(offset_of!(NativeFutexWaiter, flags) == 16);
    assert!(offset_of!(NativeFutexWaiter, reserved) == 20);
};

impl From<FutexWaiter<'_>> for NativeFutexWaiter {
    fn from(entry: FutexWaiter<'_>) -> Self {
        Self {
            expected: u64::from(entry.expected),
            address: entry.word.address() as u64,
            flags: FUTEX2_PRIVATE_U32 as u32,
            reserved: 0,
        }
    }
}

/// Wait on 1 to 128 private U32 words until one wakes or the absolute
/// CLOCK_MONOTONIC deadline elapses. Success selects one notified index.
/// Recheck the synchronization predicate after any wake.
pub fn futex_waitv(
    waiters: &[FutexWaiter<'_>],
    deadline: Option<Timespec>,
) -> Result<usize, SyscallError> {
    if !(1..=MAX_WAITERS).contains(&waiters.len()) {
        return Err(SyscallError::InvalidInput(
            "futex vector must contain 1 to 128 entries",
        ));
    }
    let pointer = timeout_pointer(deadline.as_ref())?;
    let native: Vec<_> = waiters
        .iter()
        .copied()
        .map(NativeFutexWaiter::from)
        .collect();
    // Every word remains borrowed and the array remains live for this synchronous call.
    let raw = unsafe {
        abi::call(
            FUTEX_WAITV,
            [
                native.as_ptr() as usize,
                native.len(),
                0,
                pointer,
                CLOCK_MONOTONIC as usize,
                0,
            ],
        )
    };
    let index = decode_nonnegative(raw)?;
    if index < native.len() {
        Ok(index)
    } else {
        Err(SyscallError::UnexpectedReturn(raw))
    }
}

/// If `source` still equals `expected`, wake up to `wake_count` waiting
/// threads on it, then move up to `requeue_count` remaining waiters to
/// `destination`. Returns the total affected. Normal waiters must recheck
/// their synchronization predicate on wake. Keep the destination live in
/// the same protocol until the moved waiters leave its queue.
pub fn futex_requeue(
    source: &FutexWord,
    destination: &FutexWord,
    expected: u32,
    wake_count: u32,
    requeue_count: u32,
) -> Result<u32, SyscallError> {
    if std::ptr::eq(source, destination) {
        return Err(SyscallError::InvalidInput(
            "futex requeue requires distinct source and destination words",
        ));
    }
    let maximum = wake_count
        .checked_add(requeue_count)
        .filter(|count| *count <= i32::MAX as u32)
        .ok_or(SyscallError::InvalidInput(
            "futex requeue total exceeds i32::MAX",
        ))?;
    let native = [
        NativeFutexWaiter::from(FutexWaiter::new(source, expected)),
        NativeFutexWaiter::from(FutexWaiter::new(destination, 0)),
    ];
    // The descriptors and both borrowed atomic words live through the
    // call. The non-PI requeue keeps only the private key for moved waiters.
    let raw = unsafe {
        abi::call(
            FUTEX_REQUEUE,
            [
                native.as_ptr() as usize,
                0,
                wake_count as usize,
                requeue_count as usize,
                0,
                0,
            ],
        )
    };
    woken(raw, maximum as usize)
}

/// Presence and native head length of the calling thread's robust list.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct RobustListInfo {
    pub registered: bool,
    pub head_bytes: usize,
}

fn robust_list_address() -> Result<usize, SyscallError> {
    let mut address: usize = 0;
    let mut head_bytes: usize = 0;
    // Both output slots have native pointer width and live until return.
    let raw = unsafe {
        abi::call(
            GET_ROBUST_LIST,
            [
                0,
                std::ptr::from_mut(&mut address) as usize,
                std::ptr::from_mut(&mut head_bytes) as usize,
                0,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)?;
    if head_bytes != ROBUST_LIST_HEAD_BYTES {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    Ok(address)
}

/// Observe the calling thread's robust futex registration without exposing
/// the native address, dereferencing it or changing its registration.
pub fn get_robust_list() -> Result<RobustListInfo, SyscallError> {
    Ok(RobustListInfo {
        registered: robust_list_address()? != 0,
        head_bytes: ROBUST_LIST_HEAD_BYTES,
    })
}

#[repr(C)]
struct NativeRobustListHead {
    next: usize,
    futex_offset: isize,
    list_op_pending: usize,
}

const _: () = {
    assert!(size_of::<NativeRobustListHead>() == ROBUST_LIST_HEAD_BYTES);
    assert!(align_of::<NativeRobustListHead>() == 8);
    assert!(offset_of!(NativeRobustListHead, next) == 0);
    assert!(offset_of!(NativeRobustListHead, futex_offset) == 8);
    assert!(offset_of!(NativeRobustListHead, list_op_pending) == 16);
};

#[derive(Debug)]
pub enum RobustListScopeError {
    WorkerStart(std::io::Error),
    WorkerPanicked,
    Inspect(SyscallError),
    Register(SyscallError),
    Restore(SyscallError),
}

impl fmt::Display for RobustListScopeError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::WorkerStart(error) => write!(formatter, "start robust-list worker: {error}"),
            Self::WorkerPanicked => formatter.write_str("robust-list worker panicked"),
            Self::Inspect(error) => write!(formatter, "inspect worker robust list: {error}"),
            Self::Register(error) => write!(formatter, "register worker robust list: {error}"),
            Self::Restore(error) => write!(formatter, "restore worker robust list: {error}"),
        }
    }
}

impl std::error::Error for RobustListScopeError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::WorkerStart(error) => Some(error),
            Self::WorkerPanicked => None,
            Self::Inspect(error) | Self::Register(error) | Self::Restore(error) => Some(error),
        }
    }
}

fn register_robust_list(address: usize) -> Result<(), SyscallError> {
    // The caller must keep the head live until restoration or worker exit.
    let raw = unsafe {
        abi::call(
            SET_ROBUST_LIST,
            [address, ROBUST_LIST_HEAD_BYTES, 0, 0, 0, 0],
        )
    };
    decode_zero(raw)
}

struct RobustListRegistration {
    previous: usize,
    head: Option<Box<NativeRobustListHead>>,
}

impl RobustListRegistration {
    fn begin(previous: usize) -> Result<Self, RobustListScopeError> {
        let mut head = Box::new(NativeRobustListHead {
            next: 0,
            futex_offset: 0,
            list_op_pending: 0,
        });
        let address = std::ptr::from_mut(head.as_mut()) as usize;
        head.next = address; // An empty list links back to its own first field.
        if let Err(error) = register_robust_list(address) {
            if matches!(error, SyscallError::UnexpectedReturn(_)) {
                // Keep the head live if the response did not establish that setup failed.
                Box::leak(head);
            }
            return Err(RobustListScopeError::Register(error));
        }
        Ok(Self {
            previous,
            head: Some(head),
        })
    }

    fn restore(&mut self) -> Result<(), SyscallError> {
        let Some(head) = self.head.take() else {
            return Ok(());
        };
        let restored = register_robust_list(self.previous).and_then(|()| {
            if robust_list_address()? == self.previous {
                Ok(())
            } else {
                Err(SyscallError::UnexpectedReturn(0))
            }
        });
        if restored.is_err() {
            // Keep the head live unless observation confirms its replacement.
            Box::leak(head);
        }
        restored
    }
}

impl Drop for RobustListRegistration {
    fn drop(&mut self) {
        let _ = self.restore();
    }
}

/// Temporarily register an owned empty robust list on a dedicated native thread.
/// Observe its registration, restore the original head and join the worker.
/// The caller's registration is untouched. A failed restoration retains the
/// head allocation so that Linux can still read the list at thread exit.
pub fn set_robust_list() -> Result<RobustListInfo, RobustListScopeError> {
    std::thread::Builder::new()
        .spawn(|| {
            let previous = robust_list_address().map_err(RobustListScopeError::Inspect)?;
            let mut registration = RobustListRegistration::begin(previous)?;
            let current = robust_list_address().and_then(|observed| {
                let head = registration
                    .head
                    .as_deref()
                    .ok_or(SyscallError::UnexpectedReturn(0))?;
                if observed == std::ptr::from_ref(head) as usize {
                    Ok(RobustListInfo {
                        registered: true,
                        head_bytes: ROBUST_LIST_HEAD_BYTES,
                    })
                } else {
                    Err(SyscallError::UnexpectedReturn(0))
                }
            });
            registration
                .restore()
                .map_err(RobustListScopeError::Restore)?;
            current.map_err(RobustListScopeError::Inspect)
        })
        .map_err(RobustListScopeError::WorkerStart)?
        .join()
        .map_err(|_| RobustListScopeError::WorkerPanicked)?
}

#[cfg(test)]
mod robust_registration_tests {
    use super::*;

    #[test]
    fn robust_list_scope_restores_exact_original_head() {
        std::thread::spawn(|| {
            let previous = robust_list_address().unwrap();
            let mut registration = RobustListRegistration::begin(previous).unwrap();
            let temporary = robust_list_address().unwrap();
            assert_ne!(temporary, previous);
            let head = registration.head.as_deref().unwrap();
            assert_eq!(temporary, std::ptr::from_ref(head) as usize);
            assert_eq!(head.next, temporary);
            assert_eq!(head.list_op_pending, 0);
            registration.restore().unwrap();
            assert_eq!(robust_list_address().unwrap(), previous);
        })
        .join()
        .unwrap();
    }

    #[test]
    fn robust_list_scope_restores_during_unwind() {
        std::thread::spawn(|| {
            let previous = robust_list_address().unwrap();
            let result = std::panic::catch_unwind(|| {
                let _registration = RobustListRegistration::begin(previous).unwrap();
                assert_ne!(robust_list_address().unwrap(), previous);
                panic!("unwind with an active robust-list registration");
            });
            assert!(result.is_err());
            assert_eq!(robust_list_address().unwrap(), previous);
        })
        .join()
        .unwrap();
    }

    #[test]
    fn robust_list_scope_retains_head_on_kernel_restore_refusal() {
        const MARKER: &str = "LLMLANG_ROBUST_RESTORE_DENIAL_CHILD";
        const CASE: &str = "futex::robust_registration_tests::robust_list_scope_retains_head_on_kernel_restore_refusal";
        if std::env::var_os(MARKER).is_none() {
            let output = std::process::Command::new(std::env::current_exe().unwrap())
                .args(["--exact", CASE, "--nocapture"])
                .env(MARKER, "1")
                .output()
                .unwrap();
            assert!(
                output.status.success(),
                "restore-denial child failed: {}\n{}",
                String::from_utf8_lossy(&output.stdout),
                String::from_utf8_lossy(&output.stderr)
            );
            return;
        }

        #[repr(C)]
        struct FilterInstruction {
            code: u16,
            jump_true: u8,
            jump_false: u8,
            value: u32,
        }
        #[repr(C)]
        struct FilterProgram {
            count: u16,
            filters: *const FilterInstruction,
        }

        for errno in [1_u32, 0] {
            std::thread::spawn(move || {
                let previous = robust_list_address().unwrap();
                let mut registration = RobustListRegistration::begin(previous).unwrap();
                let temporary = robust_list_address().unwrap();
                assert_ne!(temporary, previous);

                let instruction = |code, value, jump_false| FilterInstruction {
                    code,
                    value,
                    jump_true: 0,
                    jump_false,
                };
                let filters = [
                    instruction(0x20, 0, 0), // Load the syscall number.
                    instruction(0x15, SET_ROBUST_LIST as u32, 1),
                    instruction(0x06, 0x0005_0000 | errno, 0), // SECCOMP_RET_ERRNO | data.
                    instruction(0x06, 0x7fff_0000, 0),         // SECCOMP_RET_ALLOW.
                ];
                let program = FilterProgram {
                    count: filters.len() as u16,
                    filters: filters.as_ptr(),
                };
                // Install a restrictive filter on this isolated worker, without TSYNC.
                unsafe {
                    assert_eq!(abi::call(abi::PRCTL, [38, 1, 0, 0, 0, 0]), 0);
                    assert_eq!(
                        abi::call(
                            abi::PRCTL,
                            [22, 2, std::ptr::from_ref(&program) as usize, 0, 0, 0]
                        ),
                        0
                    );
                }

                let error = registration.restore().unwrap_err();
                if errno == 0 {
                    assert_eq!(error, SyscallError::UnexpectedReturn(0));
                } else {
                    assert!(error.is_errno(errno as i32));
                }
                assert_eq!(robust_list_address().unwrap(), temporary);
                assert!(registration.head.is_none());
            })
            .join()
            .unwrap();
        }
    }
}
