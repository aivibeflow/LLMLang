// Included as source in the temporary translation unit.
#![allow(dead_code, non_camel_case_types)]

use std::arch::asm;
use std::ffi::CString;

type ExitStatus = i32;
type LaunchArgs = Vec<Vec<u8>>;
type I32 = i32;
type AbiResult = isize;
type IoResult = Result<(), I32>;
type Utf8<'a> = &'a str;
type U32 = u32;
type Usize = usize;
type MutPtr<T> = *mut T;
type sockaddr = u8;

const EINTR: isize = 4;
const AT_FDCWD: i32 = -100;
const O_RDONLY: i32 = 0;
const O_WRONLY: i32 = 1;
const O_CREAT: i32 = 0o100;
const O_EXCL: i32 = 0o200;
const O_CLOEXEC: i32 = 0o2000000;
const POLLIN: i16 = 1;
const AF_INET: i32 = 2;
const SOCK_STREAM: i32 = 1;
const SOCK_CLOEXEC: i32 = O_CLOEXEC;

#[repr(C)]
struct pollfd {
    fd: i32,
    events: i16,
    revents: i16,
}

#[repr(C)]
struct sockaddr_in {
    family: u16,
    port: u16,
    address: [u8; 4],
    padding: [u8; 8],
}

impl sockaddr_in {
    fn loopback(port: u16) -> Self {
        Self {
            family: AF_INET as u16,
            port: port.to_be(),
            address: [127, 0, 0, 1],
            padding: [0; 8],
        }
    }
}

fn errno_message(errno: isize) -> Vec<u8> {
    format!("Error: Kernel(Errno({errno}))\n").into_bytes()
}

fn write_utf8(fd: I32, utf8: Utf8<'_>) -> IoResult {
    let mut remaining = utf8.as_bytes();
    while !remaining.is_empty() {
        let written = unsafe {
            raw_syscall(
                1,
                [
                    fd as usize,
                    remaining.as_ptr() as usize,
                    remaining.len(),
                    0,
                    0,
                    0,
                ],
            )
        };
        match written {
            n if n == -EINTR => continue,
            n if n < 0 => return Err(-n as I32),
            0 => return Err(5), // EIO: the write made no progress.
            n => remaining = &remaining[n as usize..],
        }
    }
    Ok(())
}

unsafe fn invoke_syscall(number: Usize, words: [Usize; 6]) -> AbiResult {
    if matches!(number, 15 | 58 | 335) {
        return -38; // ENOSYS: these calls need dedicated continuation profiles.
    }
    unsafe { raw_syscall(number, words) }
}

unsafe fn raw_syscall(number: usize, args: [usize; 6]) -> isize {
    let mut result = number as isize;
    unsafe {
        asm!(
            "syscall",
            inlateout("rax") result,
            in("rdi") args[0], in("rsi") args[1], in("rdx") args[2],
            in("r10") args[3], in("r8") args[4], in("r9") args[5],
            lateout("rcx") _, lateout("r11") _, options(nostack),
        );
    }
    result
}
