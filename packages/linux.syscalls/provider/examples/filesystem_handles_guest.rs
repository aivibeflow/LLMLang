//! Exercise global sync and privilege-requiring file handles only in the guest.
use linux_syscalls_provider::*;
use std::fs::{self, File};
use std::os::fd::AsFd;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    assert!(std::env::args()
        .skip(1)
        .eq(["--llmlang-disposable-guest-probe"]));
    assert_eq!(getppid()?, 1, "run through the disposable guest init");

    let mut namespace = unshare_mount_private()?;
    let path = "/llmlang-handles";
    fs::create_dir(path)?;
    let target = File::open(path)?;
    let mut mount = mount_tmpfs(&mut namespace, target.as_fd())?;
    let file = "/llmlang-handles/original";
    fs::write(file, b"owned tmpfs data")?;
    sync()?;
    assert_eq!(fs::read(file)?, b"owned tmpfs data");
    println!("LLMLANG_GUEST_CASE sync_completes_for_disposable_guest");

    let first = name_to_handle_at(&mount, c"original")?;
    assert!(first.mount_id() > 0);
    assert!(name_to_handle_at(&mount, c"../probe")
        .unwrap_err()
        .is_errno(18));
    assert!(matches!(
        name_to_handle_at(&mount, c"."),
        Err(SyscallError::InvalidInput(_))
    ));
    println!("LLMLANG_GUEST_CASE file_handle_resolution_stays_within_owned_tmpfs");

    fs::rename(file, "/llmlang-handles/renamed")?;
    fs::write(file, b"replacement")?;
    let second = name_to_handle_at(&mount, c"original")?;
    assert_eq!(first.mount_id(), second.mount_id());
    let reopened = open_by_handle_at(&first)?;
    assert_eq!(fcntl_getfd(reopened.borrow())? & 1, 1);
    assert_eq!(fcntl_getfl(reopened.borrow())? & 3, O_RDONLY);
    let mut bytes = [0u8; 64];
    let ReadOutcome::Progress(count) = read(reopened.borrow(), &mut bytes)? else {
        panic!("reopened handle lost its file contents");
    };
    assert_eq!(&bytes[..count], b"owned tmpfs data");
    assert_eq!(fs::read(file)?, b"replacement");
    close(reopened)?;
    drop((first, second));
    println!("LLMLANG_GUEST_CASE file_handle_reopens_original_inode_read_only_after_rename");

    umount2_tmpfs(&mut mount)?;
    Ok(())
}
