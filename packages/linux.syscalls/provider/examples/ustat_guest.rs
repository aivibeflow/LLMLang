//! Compare legacy filesystem counts with statfs on a disposable owned tmpfs.
use linux_syscalls_provider::*;
use std::fs::{self, File};
use std::os::fd::AsFd;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    assert!(std::env::args()
        .skip(1)
        .eq(["--llmlang-disposable-guest-probe"]));
    assert_eq!(getppid()?, 1, "run through the disposable guest init");

    let mut namespace = unshare_mount_private()?;
    let path = "/llmlang-ustat";
    fs::create_dir(path)?;
    let target = File::open(path)?;
    let mut mount = mount_tmpfs(&mut namespace, target.as_fd())?;
    let file_path = "/llmlang-ustat/file";
    fs::write(file_path, vec![1u8; 4096])?;
    let file = File::open(file_path)?;
    assert_eq!(lseek(file.as_fd(), 17, SeekOrigin::Start)?, 17);
    let filesystem = fstatfs(file.as_fd())?;
    let legacy = ustat(file.as_fd())?;
    assert!(filesystem.blocks_free > 0);
    assert_eq!(legacy.free_blocks, filesystem.blocks_free as i32);
    assert_eq!(legacy.free_inodes, filesystem.files_free);
    assert_eq!(legacy.filesystem_name, [0; 6]);
    assert_eq!(legacy.filesystem_pack, [0; 6]);
    assert_eq!(lseek(file.as_fd(), 0, SeekOrigin::Current)?, 17);

    fs::write("/llmlang-ustat/second", vec![2u8; 8192])?;
    let changed = ustat(file.as_fd())?;
    let current = fstatfs(file.as_fd())?;
    assert!(changed.free_blocks < legacy.free_blocks);
    assert_eq!(changed.free_blocks, current.blocks_free as i32);
    assert_eq!(changed.free_inodes, current.files_free);
    println!("LLMLANG_GUEST_CASE ustat_matches_owned_tmpfs_and_observes_allocation");
    umount2_tmpfs(&mut mount)?;
    Ok(())
}
