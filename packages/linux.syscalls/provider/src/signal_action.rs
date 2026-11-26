//! Fixed native handler probes in a disposable Linux child.
use std::arch::{asm, global_asm};
use std::fmt;
use std::mem::{align_of, offset_of, size_of};
use std::os::fd::AsRawFd;
use std::ptr;
use std::sync::atomic::{AtomicUsize, Ordering};

use crate::legacy_time::{GETITIMER, SETITIMER};
use crate::signal_control::TGKILL;
use crate::signal_fd::{RT_SIGPENDING, RT_SIGPROCMASK};
use crate::signal_wait::{raw_signal_wait, NativeSignalInfo};
use crate::system::GETUID;
use crate::{
    abi, decode_zero, fork, pipe2, read, wait4, ForkOutcome, IntervalDuration, IntervalSettings,
    IntervalTimer, ReadOutcome, SyscallError, Timespec, UserSignal, EINTR,
};

const RT_SIGACTION: usize = 13;
const RT_SIGRETURN: usize = 15;
const PAUSE: usize = 34;
const RT_SIGQUEUEINFO: usize = 129;
const RT_SIGSUSPEND: usize = 130;
const RT_TGSIGQUEUEINFO: usize = 297;
const SIGALRM: usize = 14;
const SIGALTSTACK: usize = 131;
const SIG_UNBLOCK: usize = 1;
const SIG_SETMASK: usize = 2;
const SA_RESTORER: usize = 0x0400_0000;
const SA_ONSTACK: usize = 0x0800_0000;
const MASK_BYTES: usize = size_of::<u64>();
const BLOCK_ALL: u64 = u64::MAX & !((1 << 8) | (1 << 18)); // Exclude SIGKILL and SIGSTOP.
const ALT_STACK_WORDS: usize = 4096;
const REPORT_BYTES: usize = 2 * size_of::<u64>();

// This entry runs only as the kernel-installed disposition's restorer.
// There is no callable interface for supplying a signal context.
global_asm!(
    ".pushsection .text.llmlang_fixed_signal_restorer,\"ax\",@progbits",
    ".p2align 4",
    ".global llmlang_fixed_signal_restorer",
    ".hidden llmlang_fixed_signal_restorer",
    ".type llmlang_fixed_signal_restorer,@function",
    "llmlang_fixed_signal_restorer:",
    "mov eax, {operation}",
    "syscall",
    "ud2",
    ".size llmlang_fixed_signal_restorer, .-llmlang_fixed_signal_restorer",
    ".popsection",
    operation = const RT_SIGRETURN,
);

unsafe extern "C" {
    fn llmlang_fixed_signal_restorer();
}

#[repr(C)]
#[derive(Default, Eq, PartialEq)]
struct NativeSignalAction {
    handler: usize,
    flags: usize,
    restorer: usize,
    mask: u64,
}

#[repr(C)]
#[derive(Default)]
struct NativeSignalStack {
    address: usize,
    flags: i32,
    padding: u32,
    length: usize,
}

const _: () = {
    assert!(size_of::<NativeSignalAction>() == 32);
    assert!(align_of::<NativeSignalAction>() == 8);
    assert!(offset_of!(NativeSignalAction, flags) == 8);
    assert!(offset_of!(NativeSignalAction, restorer) == 16);
    assert!(offset_of!(NativeSignalAction, mask) == 24);
    assert!(size_of::<NativeSignalStack>() == 24);
    assert!(align_of::<NativeSignalStack>() == 8);
    assert!(offset_of!(NativeSignalStack, flags) == 8);
    assert!(offset_of!(NativeSignalStack, length) == 16);
};

static OBSERVED_SIGNAL: AtomicUsize = AtomicUsize::new(0);
static OBSERVED_STACK: AtomicUsize = AtomicUsize::new(0);

extern "C" fn fixed_handler(signal: i32) {
    let stack: usize;
    unsafe { asm!("mov {}, rsp", out(reg) stack, options(nomem, nostack, preserves_flags)) };
    OBSERVED_STACK.store(stack, Ordering::Relaxed);
    OBSERVED_SIGNAL.store(signal as usize, Ordering::Release);
}

#[derive(Debug)]
pub enum SignalActionScopeError {
    WorkerStart(std::io::Error),
    WorkerPanicked,
    Parent(SyscallError),
    Child(SyscallError),
    Observation,
}

impl fmt::Display for SignalActionScopeError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::WorkerStart(error) => write!(formatter, "start signal-action worker: {error}"),
            Self::WorkerPanicked => formatter.write_str("signal-action worker panicked"),
            Self::Parent(error) => write!(formatter, "signal-action worker: {error}"),
            Self::Child(error) => write!(formatter, "isolated signal-action child: {error}"),
            Self::Observation => formatter.write_str("isolated signal-action observation failed"),
        }
    }
}

impl std::error::Error for SignalActionScopeError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::WorkerStart(error) => Some(error),
            Self::Parent(error) | Self::Child(error) => Some(error),
            Self::WorkerPanicked | Self::Observation => None,
        }
    }
}

fn raw_mask(how: usize, mask: &u64, old: *mut u64) -> isize {
    unsafe {
        abi::call(
            RT_SIGPROCMASK,
            [
                how,
                ptr::from_ref(mask) as usize,
                old as usize,
                MASK_BYTES,
                0,
                0,
            ],
        )
    }
}

fn inspect_mask(output: &mut u64) -> isize {
    unsafe {
        abi::call(
            RT_SIGPROCMASK,
            [
                SIG_SETMASK,
                0,
                ptr::from_mut(output) as usize,
                MASK_BYTES,
                0,
                0,
            ],
        )
    }
}

struct WorkerMask(Option<u64>);

impl WorkerMask {
    fn block_before_fork() -> Result<Self, SyscallError> {
        let mut previous = 0;
        decode_zero(raw_mask(
            SIG_SETMASK,
            &BLOCK_ALL,
            ptr::from_mut(&mut previous),
        ))?;
        let restoration = Self(Some(previous));
        let mut observed = 0;
        decode_zero(inspect_mask(&mut observed))?;
        if observed != BLOCK_ALL {
            return Err(SyscallError::UnexpectedReturn(0));
        }
        Ok(restoration)
    }

    fn restore(&mut self) -> Result<(), SyscallError> {
        if let Some(mask) = self.0.take() {
            decode_zero(raw_mask(SIG_SETMASK, &mask, ptr::null_mut()))?;
            let mut observed = 0;
            decode_zero(inspect_mask(&mut observed))?;
            if observed != mask {
                return Err(SyscallError::UnexpectedReturn(0));
            }
        }
        Ok(())
    }
}

impl Drop for WorkerMask {
    fn drop(&mut self) {
        let _ = self.restore();
    }
}

enum ChildFailure {
    Native(isize),
    Observation,
}

fn child_zero(raw: isize) -> Result<(), ChildFailure> {
    if raw == 0 {
        Ok(())
    } else {
        Err(ChildFailure::Native(raw))
    }
}

fn raw_action(signal: usize, action: &NativeSignalAction, old: *mut NativeSignalAction) -> isize {
    unsafe {
        abi::call(
            RT_SIGACTION,
            [
                signal,
                ptr::from_ref(action) as usize,
                old as usize,
                MASK_BYTES,
                0,
                0,
            ],
        )
    }
}

fn inspect_action(signal: usize, output: &mut NativeSignalAction) -> isize {
    unsafe {
        abi::call(
            RT_SIGACTION,
            [signal, 0, ptr::from_mut(output) as usize, MASK_BYTES, 0, 0],
        )
    }
}

fn signal_bit(signal: usize) -> u64 {
    1_u64 << (signal.wrapping_sub(1) & 63)
}

fn with_fixed_action(
    signal: usize,
    alternate: bool,
    callback: impl FnOnce() -> Result<(), ChildFailure>,
) -> Result<(), ChildFailure> {
    let mut old = NativeSignalAction::default();
    let fixed = NativeSignalAction {
        handler: fixed_handler as *const () as usize,
        flags: SA_RESTORER | if alternate { SA_ONSTACK } else { 0 },
        restorer: llmlang_fixed_signal_restorer as *const () as usize,
        mask: BLOCK_ALL,
    };
    OBSERVED_SIGNAL.store(0, Ordering::Relaxed);
    OBSERVED_STACK.store(0, Ordering::Relaxed);
    child_zero(raw_action(signal, &fixed, ptr::from_mut(&mut old)))?;

    let result = (|| {
        let mut installed = NativeSignalAction::default();
        child_zero(inspect_action(signal, &mut installed))?;
        if installed != fixed {
            return Err(ChildFailure::Observation);
        }
        callback()
    })();

    // Block the selected signal again before restoring an inherited handler.
    child_zero(raw_mask(SIG_SETMASK, &BLOCK_ALL, ptr::null_mut()))?;
    let mut restored_mask = 0;
    child_zero(inspect_mask(&mut restored_mask))?;
    if restored_mask != BLOCK_ALL {
        return Err(ChildFailure::Observation);
    }
    child_zero(raw_action(signal, &old, ptr::null_mut()))?;
    let mut restored_action = NativeSignalAction::default();
    child_zero(inspect_action(signal, &mut restored_action))?;
    if restored_action != old {
        return Err(ChildFailure::Observation);
    }
    result
}

fn child_pid() -> Result<i32, ChildFailure> {
    let raw = unsafe { abi::call(abi::GETPID, [0; 6]) };
    if raw <= 0 || raw > i32::MAX as isize {
        return Err(ChildFailure::Native(raw));
    }
    Ok(raw as i32)
}

fn child_self_signal(signal: usize) -> Result<(), ChildFailure> {
    let pid = child_pid()? as usize;
    // The isolated fork child is its own only thread and thread-group leader.
    child_zero(unsafe { abi::call(TGKILL, [pid, pid, signal, 0, 0, 0]) })
}

fn verify_return(signal: usize, expected_mask: u64) -> Result<(), ChildFailure> {
    let mut returned_mask = 0;
    child_zero(inspect_mask(&mut returned_mask))?;
    if OBSERVED_SIGNAL.load(Ordering::Acquire) != signal || returned_mask != expected_mask {
        return Err(ChildFailure::Observation);
    }
    Ok(())
}

fn child_deliver(
    signal: UserSignal,
    alternate: Option<&NativeSignalStack>,
) -> Result<(), ChildFailure> {
    let signal = signal as usize;
    let bit = signal_bit(signal);
    with_fixed_action(signal, alternate.is_some(), || {
        child_zero(raw_mask(SIG_UNBLOCK, &bit, ptr::null_mut()))?;
        child_self_signal(signal)?;
        verify_return(signal, BLOCK_ALL & !bit)?;
        if let Some(stack) = alternate {
            let used = OBSERVED_STACK.load(Ordering::Relaxed);
            if used.wrapping_sub(stack.address) >= stack.length {
                return Err(ChildFailure::Observation);
            }
        }
        Ok(())
    })
}

fn expect_interruption(raw: isize) -> Result<(), ChildFailure> {
    match raw {
        value if value == -(EINTR as isize) => Ok(()),
        0 => Err(ChildFailure::Observation),
        value => Err(ChildFailure::Native(value)),
    }
}

fn child_suspend(signal: UserSignal) -> Result<(), ChildFailure> {
    let signal = signal as usize;
    let bit = signal_bit(signal);
    with_fixed_action(signal, false, || {
        child_self_signal(signal)?;
        let mut pending = 0_u64;
        child_zero(unsafe {
            abi::call(
                RT_SIGPENDING,
                [ptr::from_mut(&mut pending) as usize, MASK_BYTES, 0, 0, 0, 0],
            )
        })?;
        if pending & bit == 0 {
            return Err(ChildFailure::Observation);
        }
        let temporary_mask = BLOCK_ALL & !bit;
        expect_interruption(unsafe {
            abi::call(
                RT_SIGSUSPEND,
                [
                    ptr::from_ref(&temporary_mask) as usize,
                    MASK_BYTES,
                    0,
                    0,
                    0,
                    0,
                ],
            )
        })?;
        verify_return(signal, BLOCK_ALL)
    })
}

fn raw_timer_write(next: &IntervalSettings, old: *mut IntervalSettings) -> isize {
    unsafe {
        abi::call(
            SETITIMER,
            [
                IntervalTimer::Real as usize,
                ptr::from_ref(next) as usize,
                old as usize,
                0,
                0,
                0,
            ],
        )
    }
}

fn raw_timer_read(output: &mut IntervalSettings) -> isize {
    unsafe {
        abi::call(
            GETITIMER,
            [
                IntervalTimer::Real as usize,
                ptr::from_mut(output) as usize,
                0,
                0,
                0,
                0,
            ],
        )
    }
}

fn child_pause() -> Result<(), ChildFailure> {
    let bit = signal_bit(SIGALRM);
    with_fixed_action(SIGALRM, false, || {
        let tick = IntervalDuration::new(0, 10_000).map_err(|_| ChildFailure::Observation)?;
        let armed = IntervalSettings {
            interval: tick,
            remaining: tick,
        };
        let mut old = IntervalSettings::default();
        child_zero(raw_timer_write(&armed, ptr::from_mut(&mut old)))?;
        let result = (|| {
            let mut before_pause = IntervalSettings::default();
            child_zero(raw_timer_read(&mut before_pause))?;
            // An expired blocked tick can be ready for delivery already.
            // Linux rearms this periodic timer when the signal is dequeued.
            if old != IntervalSettings::default() || before_pause.interval != tick {
                return Err(ChildFailure::Observation);
            }
            child_zero(raw_mask(SIG_UNBLOCK, &bit, ptr::null_mut()))?;
            expect_interruption(unsafe { abi::call(PAUSE, [0; 6]) })?;
            verify_return(SIGALRM, BLOCK_ALL & !bit)
        })();
        child_zero(raw_timer_write(&old, ptr::null_mut()))?;
        let mut restored = armed;
        child_zero(raw_timer_read(&mut restored))?;
        if restored != old {
            return Err(ChildFailure::Observation);
        }
        result
    })
}

fn child_queue(signal: UserSignal, value: i32, thread_only: bool) -> Result<(), ChildFailure> {
    let pid = child_pid()?;
    let raw_uid = unsafe { abi::call(GETUID, [0; 6]) };
    let uid = u32::try_from(raw_uid).map_err(|_| ChildFailure::Native(raw_uid))?;
    let supplied = NativeSignalInfo::self_queue(signal, pid, uid, value);
    let address = ptr::from_ref(&supplied) as usize;
    let raw = if thread_only {
        // The child is its sole thread, with matching PID and TID.
        unsafe {
            abi::call(
                RT_TGSIGQUEUEINFO,
                [pid as usize, pid as usize, signal as usize, address, 0, 0],
            )
        }
    } else {
        unsafe {
            abi::call(
                RT_SIGQUEUEINFO,
                [pid as usize, signal as usize, address, 0, 0, 0],
            )
        }
    };
    child_zero(raw)?;

    let bit = signal_bit(signal as usize);
    let mut observed = NativeSignalInfo::empty();
    let raw = raw_signal_wait(&bit, &mut observed, Some(&Timespec::default()));
    if raw != signal as isize {
        return if raw == 0 {
            Err(ChildFailure::Observation)
        } else {
            Err(ChildFailure::Native(raw))
        };
    }
    if !observed.matches_queue(signal, pid, uid, value) {
        return Err(ChildFailure::Observation);
    }
    Ok(())
}

#[derive(Clone, Copy)]
enum Probe {
    Action(UserSignal),
    AltStack(UserSignal),
    Pause,
    Suspend(UserSignal),
    Queue {
        signal: UserSignal,
        value: i32,
        thread_only: bool,
    },
}

fn child_roundtrip(
    signal: UserSignal,
    alternate: Option<&NativeSignalStack>,
) -> Result<(), ChildFailure> {
    if let Some(stack) = alternate {
        let mut old = NativeSignalStack::default();
        child_zero(unsafe {
            abi::call(
                SIGALTSTACK,
                [
                    ptr::from_ref(stack) as usize,
                    ptr::from_mut(&mut old) as usize,
                    0,
                    0,
                    0,
                    0,
                ],
            )
        })?;
        let result = child_deliver(signal, Some(stack));
        child_zero(unsafe {
            abi::call(SIGALTSTACK, [ptr::from_ref(&old) as usize, 0, 0, 0, 0, 0])
        })?;
        let mut restored = NativeSignalStack::default();
        child_zero(unsafe {
            abi::call(
                SIGALTSTACK,
                [0, ptr::from_mut(&mut restored) as usize, 0, 0, 0, 0],
            )
        })?;
        if (restored.address, restored.flags, restored.length)
            != (old.address, old.flags, old.length)
        {
            return Err(ChildFailure::Observation);
        }
        result
    } else {
        child_deliver(signal, None)
    }
}

fn finish_child(probe: Probe, alternate: Option<&NativeSignalStack>, output: usize) -> ! {
    // Up to raw exit, the child uses only stack values, lock-free atomics and
    // native syscalls. Inherited handlers remain blocked outside fixed delivery.
    let result = match probe {
        Probe::Action(signal) => child_deliver(signal, None),
        Probe::AltStack(signal) => child_roundtrip(signal, alternate),
        Probe::Pause => child_pause(),
        Probe::Suspend(signal) => child_suspend(signal),
        Probe::Queue {
            signal,
            value,
            thread_only,
        } => child_queue(signal, value, thread_only),
    };
    let report = match result {
        Ok(()) => [0_u64, 0],
        Err(ChildFailure::Native(raw)) => [raw as u64, 1],
        Err(ChildFailure::Observation) => [0, 2],
    };
    let written = unsafe {
        abi::call(
            abi::WRITE,
            [output, report.as_ptr() as usize, REPORT_BYTES, 0, 0, 0],
        )
    };
    unsafe {
        abi::call(
            abi::EXIT,
            [usize::from(written != REPORT_BYTES as isize), 0, 0, 0, 0, 0],
        )
    };
    // A denied or intercepted exit must never return to the worker's Rust runtime.
    unsafe { asm!("ud2", options(noreturn)) }
}

fn worker(probe: Probe) -> Result<(), SignalActionScopeError> {
    let (reader, writer) = pipe2(0).map_err(SignalActionScopeError::Parent)?;
    let output = writer.as_raw_fd() as usize;
    let mut storage =
        matches!(probe, Probe::AltStack(_)).then(|| Box::new([0_u128; ALT_STACK_WORDS]));
    let stack = storage.as_mut().map(|storage| NativeSignalStack {
        address: storage.as_mut_ptr() as usize,
        flags: 0,
        padding: 0,
        length: size_of::<[u128; ALT_STACK_WORDS]>(),
    });
    let mut mask = WorkerMask::block_before_fork().map_err(SignalActionScopeError::Parent)?;
    // The child never returns to this Rust worker and every inherited handler is blocked.
    let mut child = match unsafe { fork() }.map_err(SignalActionScopeError::Parent)? {
        ForkOutcome::Child => finish_child(probe, stack.as_ref(), output),
        ForkOutcome::Parent(child) => child,
    };
    let restored = mask.restore().map_err(SignalActionScopeError::Parent);
    drop(writer);
    let status = loop {
        match wait4(&mut child, 0) {
            Err(error) if error.is_errno(EINTR) => continue,
            result => break result.map_err(SignalActionScopeError::Parent),
        }
    };
    restored?;
    if status?.and_then(|status| status.exited()) != Some(0) {
        return Err(SignalActionScopeError::Observation);
    }

    let mut bytes = [0_u8; REPORT_BYTES];
    let read_result = loop {
        match read(reader.borrow(), &mut bytes) {
            Err(error) if error.is_errno(EINTR) => continue,
            result => break result.map_err(SignalActionScopeError::Parent)?,
        }
    };
    if read_result != ReadOutcome::Progress(REPORT_BYTES) {
        return Err(SignalActionScopeError::Observation);
    }
    let (raw, tag) = bytes.split_at(8);
    let raw = i64::from_ne_bytes(raw.try_into().expect("native report word")) as isize;
    match u64::from_ne_bytes(tag.try_into().expect("native report tag")) {
        0 if raw == 0 => Ok(()),
        1 if raw != 0 => decode_zero(raw).map_err(SignalActionScopeError::Child),
        _ => Err(SignalActionScopeError::Observation),
    }
}

fn run_probe(probe: Probe) -> Result<(), SignalActionScopeError> {
    std::thread::Builder::new()
        .spawn(move || worker(probe))
        .map_err(SignalActionScopeError::WorkerStart)?
        .join()
        .map_err(|_| SignalActionScopeError::WorkerPanicked)?
}

/// Install a fixed handler, deliver the selected signal and return through
/// the native restorer in an isolated child. Prior child state is restored
/// before a successful exit. The calling thread's signal state is unchanged.
pub fn rt_sigaction(signal: UserSignal) -> Result<(), SignalActionScopeError> {
    run_probe(Probe::Action(signal))
}

/// Run the fixed handler on an owned alternate stack in an isolated child.
/// Checks actual execution on the alternate stack and restores earlier state
/// before a successful exit. No stack addresses escape the scope.
pub fn sigaltstack(signal: UserSignal) -> Result<(), SignalActionScopeError> {
    run_probe(Probe::AltStack(signal))
}

/// Wait for a fixture SIGALRM using native pause in a disposable fork child.
/// Observes the fixed handler, EINTR and restoration of the prior child state.
pub fn pause() -> Result<(), SignalActionScopeError> {
    run_probe(Probe::Pause)
}

/// Temporarily unblock a selected pending signal with native rt_sigsuspend
/// in a disposable fork child. Verifies EINTR and restoration of the old mask.
pub fn rt_sigsuspend(signal: UserSignal) -> Result<(), SignalActionScopeError> {
    run_probe(Probe::Suspend(signal))
}

/// Queue and consume a process-directed SI_QUEUE integer signal in an
/// isolated child. The kernel observes the child's own PID and real UID.
pub fn rt_sigqueueinfo(signal: UserSignal, value: i32) -> Result<(), SignalActionScopeError> {
    run_probe(Probe::Queue {
        signal,
        value,
        thread_only: false,
    })
}

/// Queue and consume a thread-directed SI_QUEUE integer signal in an
/// isolated child. The only target is that child's sole calling thread.
pub fn rt_tgsigqueueinfo(signal: UserSignal, value: i32) -> Result<(), SignalActionScopeError> {
    run_probe(Probe::Queue {
        signal,
        value,
        thread_only: true,
    })
}
