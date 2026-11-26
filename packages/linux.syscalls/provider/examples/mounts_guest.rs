use linux_syscalls_provider::{
    capset_clear, chroot_tmpfs, close, fcntl_getfd, fspick, getppid, mount_setattr, mount_tmpfs,
    open_tree, openat, pivot_root_tmpfs, read, umount2_tmpfs, unshare_mount_private,
    ChangeRootError, Directory, MountNamespaceError, OpenOptions, ReadOutcome, SyscallError,
    UnmountTmpfsError, O_RDONLY,
};
use std::ffi::{c_char, c_int, c_ulong, c_void};
use std::fs::{self, File};
use std::io::{self, Read};
use std::os::fd::AsFd;
use std::os::unix::fs::PermissionsExt;
use std::ptr;

#[repr(C)]
#[derive(Default)]
struct StatVfs {
    block_size: u64,
    fragment_size: u64,
    total_blocks: u64,
    free_blocks: u64,
    available_blocks: u64,
    total_inodes: u64,
    free_inodes: u64,
    available_inodes: u64,
    filesystem_id: u64,
    flags: u64,
    name_max: u64,
    reserved: [i32; 6],
}

extern "C" {
    fn statvfs(path: *const c_char, out: *mut StatVfs) -> i32;
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    assert_eq!(
        std::env::args().nth(1).as_deref(),
        Some("--llmlang-disposable-guest-probe")
    );
    assert_eq!(getppid()?, 1, "run through the disposable guest init");

    let original_root = File::open("/")?;
    let mut namespace = unshare_mount_private()?;
    assert!(matches!(
        unshare_mount_private(),
        Err(MountNamespaceError::AlreadyEntered)
    ));
    assert!(mount_tmpfs(&mut namespace, original_root.as_fd())
        .unwrap_err()
        .is_errno(22));
    println!("LLMLANG_GUEST_CASE mount_namespace_rejects_parent_target");

    let initial_cwd = std::env::current_dir()?;
    let directory = "llmlang-tmpfs-guest-target";
    let original_file = "llmlang-tmpfs-guest-target/original";
    let temporary_file = "llmlang-tmpfs-guest-target/temporary";
    fs::create_dir(directory)?;
    fs::write(original_file, b"underlying file")?;
    let target = File::open(directory)?;
    let mut mount = mount_tmpfs(&mut namespace, target.as_fd())?;
    assert!(!std::path::Path::new(original_file).exists());
    fs::write(temporary_file, b"temporary file")?;
    assert_eq!(fs::read(temporary_file)?, b"temporary file");
    assert_eq!(fs::metadata(directory)?.permissions().mode() & 0o777, 0o700);
    let mut mount_info = StatVfs::default();
    assert_eq!(
        unsafe { statvfs(c"llmlang-tmpfs-guest-target".as_ptr(), &mut mount_info) },
        0
    );
    const RESTRICTED_FLAGS: u64 = 2 | 4 | 8;
    assert_eq!(mount_info.flags & RESTRICTED_FLAGS, RESTRICTED_FLAGS);
    assert_eq!(mount_info.fragment_size * mount_info.total_blocks, 1048576);
    println!("LLMLANG_GUEST_CASE tmpfs_restricted_attachment");

    let context = fspick(&mount)?;
    assert_eq!(fcntl_getfd(context.as_fd())? & 1, 1);
    close(context)?;
    fs::write(temporary_file, b"temporary file")?;
    println!("LLMLANG_GUEST_CASE fspick_owns_cloexec_context_without_reconfiguring");

    std::os::unix::fs::symlink("temporary", "llmlang-tmpfs-guest-target/link")?;
    assert_eq!(
        fs::read("llmlang-tmpfs-guest-target/link")?,
        b"temporary file"
    );
    let detached = open_tree(&mount)?;
    assert_eq!(fcntl_getfd(detached.as_fd())? & 1, 1);
    assert!(std::path::Path::new(temporary_file).exists());

    mount_setattr(&mount)?;
    assert_eq!(fs::read(temporary_file)?, b"temporary file");
    assert_eq!(
        fs::write(temporary_file, b"blocked")
            .unwrap_err()
            .raw_os_error(),
        Some(30)
    );
    assert_eq!(
        fs::read("llmlang-tmpfs-guest-target/link")
            .unwrap_err()
            .raw_os_error(),
        Some(40)
    );
    assert_eq!(
        unsafe { statvfs(c"llmlang-tmpfs-guest-target".as_ptr(), &mut mount_info) },
        0
    );
    assert_eq!(
        mount_info.flags & (RESTRICTED_FLAGS | 1),
        RESTRICTED_FLAGS | 1
    );
    println!("LLMLANG_GUEST_CASE mount_setattr_tightens_only_owned_attachment");

    umount2_tmpfs(&mut mount)?;
    assert_eq!(std::env::current_dir()?, initial_cwd);
    assert!(matches!(
        umount2_tmpfs(&mut mount),
        Err(UnmountTmpfsError::AlreadyDetached)
    ));
    assert_eq!(fs::read(original_file)?, b"underlying file");
    assert!(!std::path::Path::new(temporary_file).exists());
    println!("LLMLANG_GUEST_CASE tmpfs_exact_detach_restores_cwd");

    let read_options = OpenOptions {
        flags: O_RDONLY,
        mode: 0,
    };
    let cloned_file = openat(
        Directory::Borrowed(detached.as_fd()),
        c"temporary",
        read_options,
    )?;
    let mut bytes = [0; 32];
    let ReadOutcome::Progress(count) = read(cloned_file.as_fd(), &mut bytes)? else {
        panic!("detached clone lost its source tmpfs data");
    };
    assert_eq!(&bytes[..count], b"temporary file");
    close(cloned_file)?;
    close(detached)?;
    println!("LLMLANG_GUEST_CASE open_tree_cloexec_clone_outlives_detachment");
    assert!(matches!(
        open_tree(&mount),
        Err(SyscallError::InvalidInput(_))
    ));
    assert!(matches!(fspick(&mount), Err(SyscallError::InvalidInput(_))));
    assert!(matches!(
        mount_setattr(&mount),
        Err(SyscallError::InvalidInput(_))
    ));
    println!("LLMLANG_GUEST_CASE mount_extensions_reject_detached_handle");
    drop(mount);

    let fallback = mount_tmpfs(&mut namespace, target.as_fd())?;
    assert!(!std::path::Path::new(original_file).exists());
    drop(fallback);
    assert_eq!(std::env::current_dir()?, initial_cwd);
    assert_eq!(fs::read(original_file)?, b"underlying file");
    fs::remove_file(original_file)?;
    fs::remove_dir(directory)?;
    println!("LLMLANG_GUEST_CASE tmpfs_drop_detaches");

    root_change_fixtures()?;
    Ok(())
}

fn root_change_fixtures() -> Result<(), Box<dyn std::error::Error>> {
    const TARGET: &str = "llmlang-root-change-target";
    fs::create_dir(TARGET)?;
    std::thread::spawn(|| {
        let mut namespace = unshare_mount_private().unwrap();
        let mut outside = File::open("/probe").unwrap();
        let target = File::open(TARGET).unwrap();
        let mut mount = mount_tmpfs(&mut namespace, target.as_fd()).unwrap();
        fs::write(format!("{TARGET}/owned"), b"owned tmpfs").unwrap();
        chroot_tmpfs(&mut mount).unwrap();
        assert_eq!(std::env::current_dir().unwrap().as_os_str(), "/");
        assert_eq!(fs::read("./owned").unwrap(), b"owned tmpfs");
        assert!(!std::path::Path::new("/probe").exists());
        let mut magic = [0; 4];
        outside.read_exact(&mut magic).unwrap();
        assert_eq!(magic, *b"\x7fELF");
        assert!(matches!(
            chroot_tmpfs(&mut mount),
            Err(ChangeRootError::Unavailable(_))
        ));
        println!("LLMLANG_GUEST_CASE chroot_sets_owned_root_and_cwd_and_preserves_open_fd");
    })
    .join()
    .unwrap();

    std::thread::spawn(|| {
        let mut namespace = unshare_mount_private().unwrap();
        let before = std::env::current_dir().unwrap();
        let target = File::open(TARGET).unwrap();
        let mut mount = mount_tmpfs(&mut namespace, target.as_fd()).unwrap();
        capset_clear().unwrap();
        for _ in 0..2 {
            assert!(matches!(
                chroot_tmpfs(&mut mount),
                Err(ChangeRootError::ChangeRoot(error)) if error.is_errno(1)
            ));
            assert_eq!(std::env::current_dir().unwrap(), before);
            assert!(std::path::Path::new("/probe").exists());
        }
        println!("LLMLANG_GUEST_CASE chroot_kernel_denial_restores_original_cwd");
    })
    .join()
    .unwrap();

    std::thread::spawn(|| {
        let mut namespace = unshare_mount_private().unwrap();
        let before = std::env::current_dir().unwrap();
        let target = File::open(TARGET).unwrap();
        let mut mount = mount_tmpfs(&mut namespace, target.as_fd()).unwrap();

        let marker = format!("{TARGET}/.llmlang-old-root");
        std::os::unix::fs::symlink(".", &marker).unwrap();
        assert!(matches!(
            pivot_root_tmpfs(&mut mount),
            Err(ChangeRootError::OpenOldRootDirectory(_))
        ));
        fs::remove_file(&marker).unwrap();
        fs::create_dir(marker).unwrap();
        assert!(matches!(
            pivot_root_tmpfs(&mut mount),
            Err(ChangeRootError::ChangeRoot(error)) if error.is_errno(22)
        ));
        assert_eq!(std::env::current_dir().unwrap(), before);
        umount2_tmpfs(&mut mount).unwrap();
        println!("LLMLANG_GUEST_CASE pivot_root_rejects_symlink_and_restores_cwd_on_rootfs");
    })
    .join()
    .unwrap();

    std::thread::spawn(pivot_on_attached_root).join().unwrap();
    assert!(std::path::Path::new("/probe").exists());
    fs::remove_dir(TARGET)?;
    Ok(())
}

extern "C" {
    fn mount(
        source: *const c_char,
        target: *const c_char,
        fs_type: *const c_char,
        flags: c_ulong,
        data: *const c_void,
    ) -> c_int;
    fn chroot(path: *const c_char) -> c_int;
}

fn pivot_on_attached_root() {
    let mut namespace = unshare_mount_private().unwrap();
    // The disposable guest initially uses initramfs, which pivot_root rejects.
    // An independently mounted tmpfs makes the old root an attached mount.
    let outer = c"llmlang-root-change-target";
    assert_eq!(
        unsafe {
            mount(
                c"tmpfs".as_ptr(),
                outer.as_ptr(),
                c"tmpfs".as_ptr(),
                2 | 4 | 8,
                ptr::null(),
            )
        },
        0,
        "mount fixture tmpfs: {}",
        io::Error::last_os_error()
    );
    std::env::set_current_dir(outer.to_str().unwrap()).unwrap();
    assert_eq!(unsafe { chroot(c".".as_ptr()) }, 0);
    fs::write("/old-marker", b"old tmpfs root").unwrap();
    fs::create_dir("/new").unwrap();
    let target = File::open("/new").unwrap();
    let mut mounted = mount_tmpfs(&mut namespace, target.as_fd()).unwrap();
    fs::create_dir("/new/.llmlang-old-root").unwrap();
    fs::write("/new/new-marker", b"new tmpfs root").unwrap();
    pivot_root_tmpfs(&mut mounted).unwrap();
    assert_eq!(std::env::current_dir().unwrap().as_os_str(), "/");
    assert_eq!(fs::read("./new-marker").unwrap(), b"new tmpfs root");
    assert_eq!(
        fs::read("/.llmlang-old-root/old-marker").unwrap(),
        b"old tmpfs root"
    );
    assert!(!std::path::Path::new("/old-marker").exists());
    assert!(matches!(
        pivot_root_tmpfs(&mut mounted),
        Err(ChangeRootError::Unavailable(_))
    ));
    println!("LLMLANG_GUEST_CASE pivot_root_moves_previous_attached_root_into_owned_tmpfs");
}
