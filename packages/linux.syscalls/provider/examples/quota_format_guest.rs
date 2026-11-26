//! Query quotas on the disposable runner's synthetic ext4 fixture.
use linux_syscalls_provider::{
    getppid, quotactl_fd_get_format, quotactl_get_format, QuotaFormat, QuotaKind,
};
use std::ffi::CStr;
use std::fs::{self, File, OpenOptions};
use std::io;
use std::os::fd::{AsFd, AsRawFd};
use std::os::unix::fs::OpenOptionsExt;

const FIXTURE: &str = "/quota.ext4";
const DEVICE: &CStr = c"/quota-device";
const MOUNT: &CStr = c"/quota";

const FINIT_MODULE: i64 = 313;
const LOOP_SET_FD: usize = 0x4c00;
const LOOP_CLR_FD: usize = 0x4c01;
const O_PATH: i32 = 0o10000000;
const MS_NOSUID_NODEV_NOEXEC: usize = 2 | 4 | 8;

unsafe extern "C" {
    fn syscall(number: i64, ...) -> i64;
    fn ioctl(fd: i32, request: usize, ...) -> i32;
    fn mknod(path: *const i8, mode: u32, device: u64) -> i32;
    fn mount(
        source: *const i8,
        target: *const i8,
        filesystem: *const i8,
        flags: usize,
        data: *const i8,
    ) -> i32;
    fn umount(target: *const i8) -> i32;
}

fn native_zero(value: i64) -> io::Result<()> {
    if value == 0 {
        Ok(())
    } else {
        Err(io::Error::last_os_error())
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    assert_eq!(getppid()?, 1, "run through the disposable guest init");
    assert_eq!(
        std::env::args().nth(1).as_deref(),
        Some("--llmlang-disposable-guest-probe")
    );

    let backing = OpenOptions::new().read(true).write(true).open(FIXTURE)?;
    for module in ["/loop.ko", "/quota_tree.ko", "/quota_v2.ko"] {
        let file = File::open(module)?;
        native_zero(unsafe { syscall(FINIT_MODULE, file.as_raw_fd(), c"".as_ptr(), 0_i32) })?;
    }
    fs::create_dir("/quota")?;
    // The runner starts with no attached writable disks. loop0 (7:0) is
    // configured here on the initramfs file, inside the disposable guest.
    native_zero(unsafe { mknod(DEVICE.as_ptr(), 0o060600, 7 << 8) }.into())?;
    let disk = OpenOptions::new()
        .read(true)
        .write(true)
        .open("/quota-device")?;
    native_zero(unsafe { ioctl(disk.as_raw_fd(), LOOP_SET_FD, backing.as_raw_fd()) }.into())?;
    native_zero(
        unsafe {
            mount(
                DEVICE.as_ptr(),
                MOUNT.as_ptr(),
                c"ext4".as_ptr(),
                MS_NOSUID_NODEV_NOEXEC,
                c"usrquota".as_ptr(),
            )
        }
        .into(),
    )?;

    assert_eq!(
        quotactl_get_format(DEVICE, QuotaKind::User)?,
        QuotaFormat::VfsV1
    );
    assert!(quotactl_get_format(DEVICE, QuotaKind::Group)
        .unwrap_err()
        .is_errno(3)); // ESRCH, inactive group quotas
    println!("LLMLANG_GUEST_CASE quotactl_reads_active_format_by_owned_device_path");

    let root = OpenOptions::new()
        .read(true)
        .custom_flags(O_PATH)
        .open("/quota")?;
    assert_eq!(
        quotactl_fd_get_format(root.as_fd(), QuotaKind::User)?,
        QuotaFormat::VfsV1
    );
    assert!(quotactl_fd_get_format(root.as_fd(), QuotaKind::Group)
        .unwrap_err()
        .is_errno(3));
    println!("LLMLANG_GUEST_CASE quotactl_fd_reads_active_format_through_o_path");

    drop(root);
    native_zero(unsafe { umount(MOUNT.as_ptr()) }.into())?;
    native_zero(unsafe { ioctl(disk.as_raw_fd(), LOOP_CLR_FD) }.into())?;
    Ok(())
}
