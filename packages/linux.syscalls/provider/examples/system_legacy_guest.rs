use linux_syscalls_provider::*;
use std::env;

const GUEST_ARGUMENT: &str = "--llmlang-disposable-guest-probe";

fn main() -> Result<(), SyscallError> {
    assert!(env::args().skip(1).eq([GUEST_ARGUMENT]));
    assert_eq!(getppid()?, 1, "run through the disposable guest init");
    assert!(syslog_buffer_size()? > 0);
    println!("LLMLANG_GUEST_CASE syslog_observes_capacity_without_reading_contents");
    assert!(sysfs_count()? > 0);
    println!("LLMLANG_GUEST_CASE sysfs_reports_filesystem_type_count");

    let mut owned = mmap(4096, Protection::ReadWrite)?;
    owned.as_mut_slice().unwrap()[0] = 0x7b;
    mlockall_current_onfault()?;
    assert_eq!(owned.as_slice()[0], 0x7b);
    munlockall()?;
    assert_eq!(owned.as_slice()[0], 0x7b);
    munmap(owned).unwrap();
    println!("LLMLANG_GUEST_CASE memory_lockall_and_unlockall_preserve_owned_bytes");
    Ok(())
}
