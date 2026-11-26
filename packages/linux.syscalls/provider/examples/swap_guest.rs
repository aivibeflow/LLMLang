use linux_syscalls_provider::*;
use std::ffi::c_char;
use std::fs::{self, File, OpenOptions};
use std::io::Write;
use std::os::fd::AsRawFd;
use std::process::Command;

const GUEST_ARGUMENT: &str = "--llmlang-disposable-guest-probe";
const SWAP_BLOCK_DEVICE: &std::ffi::CStr = c"/llmlang-loop0";
const LOOP_SET_FD: usize = 0x4c00;
const LOOP_CLR_FD: usize = 0x4c01;
const PAGE_SIZE: usize = 4096;
const AREA_PAGES: u32 = 4096;

extern "C" {
    fn ioctl(fd: i32, request: usize, ...) -> i32;
    fn mknod(path: *const c_char, mode: u32, dev: u64) -> i32;
    fn mount(
        source: *const c_char,
        target: *const c_char,
        fstype: *const c_char,
        flags: usize,
        data: usize,
    ) -> i32;
    fn syscall(number: isize, ...) -> isize;
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = std::env::args().skip(1).collect();
    assert_eq!(args.first().map(String::as_str), Some(GUEST_ARGUMENT));
    if args.get(1).is_some_and(|mode| mode == "unprivileged") {
        setuid(UserId::new(65534)?)?;
        assert!(swapon(SWAP_BLOCK_DEVICE).unwrap_err().is_errno(1));
        assert!(swapoff(SWAP_BLOCK_DEVICE).unwrap_err().is_errno(1));
        return Ok(());
    }
    assert_eq!(args.len(), 1);
    assert_eq!(getppid()?, 1);

    let module = File::open("/loop.ko")?;
    // The runner inserts this exact signed loop module for the booted kernel.
    assert_eq!(unsafe { syscall(313, module.as_raw_fd(), c"".as_ptr(), 0) }, 0);
    assert_eq!(unsafe { mknod(SWAP_BLOCK_DEVICE.as_ptr(), 0o60600, 7 << 8) }, 0);
    fs::create_dir("/llmlang-proc")?;
    assert_eq!(unsafe {
        mount(c"proc".as_ptr(), c"/llmlang-proc".as_ptr(), c"proc".as_ptr(), 0, 0)
    }, 0);

    let listed = || -> std::io::Result<bool> {
        Ok(fs::read_to_string("/llmlang-proc/swaps")?.lines().skip(1).any(|line| {
            line.split_whitespace().next() == Some("/llmlang-loop0")
        }))
    };
    let backing = OpenOptions::new().read(true).write(true).create_new(true)
        .open("/llmlang-swap-fixture")?;
    backing.set_len(u64::from(AREA_PAGES) * PAGE_SIZE as u64)?;
    let mut loop_device = OpenOptions::new().read(true).write(true).open("/llmlang-loop0")?;
    assert_eq!(unsafe { ioctl(loop_device.as_raw_fd(), LOOP_SET_FD, backing.as_raw_fd()) }, 0);
    assert!(!listed()?);
    assert!(swapon(SWAP_BLOCK_DEVICE).unwrap_err().is_errno(22));
    assert!(swapoff(SWAP_BLOCK_DEVICE).unwrap_err().is_errno(22));
    assert!(!listed()?);
    println!("LLMLANG_GUEST_CASE swap_invalid_header_and_inactive_area_preserve_state");

    // Write the v1 x86-64 swap header via the same device the kernel reads.
    // This updates the block cache used by the prior validation attempt.
    let mut header = [0_u8; PAGE_SIZE];
    header[1024..1028].copy_from_slice(&1_u32.to_le_bytes());
    header[1028..1032].copy_from_slice(&(AREA_PAGES - 1).to_le_bytes());
    header[PAGE_SIZE - 10..].copy_from_slice(b"SWAPSPACE2");
    loop_device.write_all(&header)?;
    loop_device.sync_all()?;

    swapon(SWAP_BLOCK_DEVICE)?;
    assert!(listed()?);
    assert!(swapon(SWAP_BLOCK_DEVICE).unwrap_err().is_errno(16));
    assert!(listed()?);
    let denied = Command::new("/probe").args([GUEST_ARGUMENT, "unprivileged"]).status()?;
    assert!(denied.success());
    assert!(listed()?);
    swapoff(SWAP_BLOCK_DEVICE)?;
    assert!(!listed()?);
    println!("LLMLANG_GUEST_CASE swap_activates_and_releases_only_owned_guest_device");
    println!("LLMLANG_GUEST_CASE swap_denial_preserves_owned_guest_device_state");

    assert_eq!(unsafe { ioctl(loop_device.as_raw_fd(), LOOP_CLR_FD) }, 0);
    Ok(())
}
