use std::arch::asm;

pub(super) const READ: usize = 0;
pub(super) const WRITE: usize = 1;
pub(super) const OPEN: usize = 2;
pub(super) const CLOSE: usize = 3;
pub(super) const POLL: usize = 7;
pub(super) const LSEEK: usize = 8;
pub(super) const MMAP: usize = 9;
pub(super) const MPROTECT: usize = 10;
pub(super) const MUNMAP: usize = 11;
pub(super) const IOCTL: usize = 16;
pub(super) const PREAD64: usize = 17;
pub(super) const PWRITE64: usize = 18;
pub(super) const READV: usize = 19;
pub(super) const WRITEV: usize = 20;
pub(super) const DUP: usize = 32;
pub(super) const MADVISE: usize = 28;
pub(super) const NANOSLEEP: usize = 35;
pub(super) const GETPID: usize = 39;
pub(super) const SOCKET: usize = 41;
pub(super) const CONNECT: usize = 42;
pub(super) const ACCEPT: usize = 43;
pub(super) const SENDTO: usize = 44;
pub(super) const RECVFROM: usize = 45;
pub(super) const SHUTDOWN: usize = 48;
pub(super) const BIND: usize = 49;
pub(super) const LISTEN: usize = 50;
pub(super) const GETSOCKNAME: usize = 51;
pub(super) const GETPEERNAME: usize = 52;
pub(super) const FORK: usize = 57;
pub(super) const EXECVE: usize = 59;
pub(super) const EXIT: usize = 60;
pub(super) const WAIT4: usize = 61;
pub(super) const FCNTL: usize = 72;
pub(super) const FLOCK: usize = 73;
pub(super) const FSYNC: usize = 74;
pub(super) const FDATASYNC: usize = 75;
pub(super) const FTRUNCATE: usize = 77;
pub(super) const FCHMOD: usize = 91;
pub(super) const PRCTL: usize = 157;
pub(super) const GETDENTS64: usize = 217;
pub(super) const CLOCK_GETTIME: usize = 228;
pub(super) const CLOCK_GETRES: usize = 229;
pub(super) const EPOLL_WAIT: usize = 232;
pub(super) const EPOLL_CTL: usize = 233;
pub(super) const OPENAT: usize = 257;
pub(super) const MKDIRAT: usize = 258;
pub(super) const UNLINKAT: usize = 263;
pub(super) const RENAMEAT: usize = 264;
pub(super) const LINKAT: usize = 265;
pub(super) const SYMLINKAT: usize = 266;
pub(super) const READLINKAT: usize = 267;
pub(super) const TIMERFD_CREATE: usize = 283;
pub(super) const TIMERFD_SETTIME: usize = 286;
pub(super) const TIMERFD_GETTIME: usize = 287;
pub(super) const ACCEPT4: usize = 288;
pub(super) const EVENTFD2: usize = 290;
pub(super) const EPOLL_CREATE1: usize = 291;
pub(super) const PIPE2: usize = 293;
pub(super) const SYNCFS: usize = 306;
pub(super) const STATX: usize = 332;
pub(super) const FACCESSAT2: usize = 439;
pub(super) const FCHMODAT2: usize = 452;

/// Invoke the native Linux x86-64 kernel ABI, preserving all raw return bits.
///
/// Callers must supply the syscall's exact arguments, layouts and valid pointers
/// for its complete memory footprint, and observe its lifetime and state rules.
#[inline]
unsafe fn enter<const NUMBER: usize>(args: [usize; 6]) -> isize {
    let result: isize;
    unsafe {
        asm!(
            "syscall",
            inlateout("rax") NUMBER => result,
            in("rdi") args[0],
            in("rsi") args[1],
            in("rdx") args[2],
            in("r10") args[3],
            in("r8") args[4],
            in("r9") args[5],
            lateout("rcx") _,
            lateout("r11") _,
            options(nostack),
        );
    }
    result
}

include!(concat!(env!("OUT_DIR"), "/native_syscalls.rs"));
