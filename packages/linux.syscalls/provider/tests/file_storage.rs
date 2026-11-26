use linux_syscalls_provider::*;
use std::fs::{self, File, OpenOptions};
use std::os::fd::AsFd;
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

const ENOENT: i32 = 2;
const EEXIST: i32 = 17;

struct Scratch(PathBuf);

impl Scratch {
    fn new() -> Self {
        static NEXT: AtomicU64 = AtomicU64::new(0);
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let number = NEXT.fetch_add(1, Ordering::Relaxed);
        let path = std::env::temp_dir().join(format!(
            "llmlang-file-storage-{}-{timestamp}-{number}",
            std::process::id()
        ));
        fs::create_dir(&path).unwrap();
        Self(path)
    }
}

impl Drop for Scratch {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

#[test]
fn native_allocation_advice_and_sync_preserve_contents_and_cursor() {
    let scratch = Scratch::new();
    let path = scratch.0.join("file");
    let prefix = b"unchanged bytes";
    fs::write(&path, prefix).unwrap();
    let file = OpenOptions::new()
        .read(true)
        .write(true)
        .open(&path)
        .unwrap();
    let fd = file.as_fd();
    assert_eq!(lseek(fd, 3, SeekOrigin::Start).unwrap(), 3);

    assert!(fallocate(fd, -1, 4096).unwrap_err().is_errno(EINVAL));
    fallocate(fd, 4096, 4096).unwrap();
    fadvise64(fd, 0, 1024, FileAdvice::Sequential).unwrap();
    fadvise64(fd, 1024, 0, FileAdvice::WillNeed).unwrap();
    readahead(fd, 0, 2048).unwrap();
    let flags = SyncFileRangeFlags::WAIT_BEFORE
        .combine(SyncFileRangeFlags::WRITE)
        .combine(SyncFileRangeFlags::WAIT_AFTER);
    assert!(sync_file_range(fd, -1, 2048, flags)
        .unwrap_err()
        .is_errno(EINVAL));
    sync_file_range(fd, 0, 0, flags).unwrap();
    assert_eq!(lseek(fd, 0, SeekOrigin::Current).unwrap(), 3);

    let contents = fs::read(&path).unwrap();
    assert_eq!(contents.len(), 8192);
    assert_eq!(&contents[..prefix.len()], prefix);
    assert!(contents[prefix.len()..].iter().all(|byte| *byte == 0));
    let writer = OpenOptions::new().write(true).open(&path).unwrap();
    assert!(readahead(writer.as_fd(), 0, 512)
        .unwrap_err()
        .is_errno(EBADF));
}

#[test]
fn native_rename_modes_enforce_atomic_name_updates() {
    let scratch = Scratch::new();
    let directory = File::open(&scratch.0).unwrap();
    let scope = Directory::Borrowed(directory.as_fd());
    let source = scratch.0.join("source");
    let destination = scratch.0.join("destination");
    let third = scratch.0.join("third");
    fs::write(&source, b"before").unwrap();
    fs::write(&destination, b"after").unwrap();

    let collision = renameat2(
        scope,
        c"source",
        scope,
        c"destination",
        RenameMode::NoReplace,
    )
    .unwrap_err();
    assert!(collision.is_errno(EEXIST));
    assert_eq!(fs::read(&source).unwrap(), b"before");
    assert_eq!(fs::read(&destination).unwrap(), b"after");
    let missing = renameat2(scope, c"source", scope, c"third", RenameMode::Exchange).unwrap_err();
    assert!(missing.is_errno(ENOENT));
    assert_eq!(fs::read(&source).unwrap(), b"before");
    assert!(!third.exists());

    renameat2(
        scope,
        c"source",
        scope,
        c"destination",
        RenameMode::Exchange,
    )
    .unwrap();
    assert_eq!(fs::read(&source).unwrap(), b"after");
    assert_eq!(fs::read(&destination).unwrap(), b"before");
    renameat2(scope, c"source", scope, c"third", RenameMode::NoReplace).unwrap();
    assert!(!source.exists());
    assert_eq!(fs::read(&third).unwrap(), b"after");
    renameat2(scope, c"third", scope, c"destination", RenameMode::Replace).unwrap();
    assert!(!third.exists());
    assert_eq!(fs::read(&destination).unwrap(), b"after");
}

#[test]
fn native_range_copy_reports_partial_progress_and_exact_offset_updates() {
    let scratch = Scratch::new();
    let source = scratch.0.join("source");
    let destination = scratch.0.join("destination");
    fs::write(&source, b"abcdefgh").unwrap();
    fs::write(&destination, b"........").unwrap();
    let input = File::open(&source).unwrap();
    let output = OpenOptions::new()
        .read(true)
        .write(true)
        .open(&destination)
        .unwrap();
    let src = input.as_fd();
    let dst = output.as_fd();
    lseek(src, 2, SeekOrigin::Start).unwrap();
    lseek(dst, 1, SeekOrigin::Start).unwrap();
    let mut read_at = 5;
    let mut write_at = 4;

    assert_eq!(
        copy_file_range(src, Some(&mut read_at), dst, Some(&mut write_at), 64).unwrap(),
        3
    );
    assert_eq!((read_at, write_at), (8, 7));
    assert_eq!(fs::read(&destination).unwrap(), b"....fgh.");
    assert_eq!(lseek(src, 0, SeekOrigin::Current).unwrap(), 2);
    assert_eq!(lseek(dst, 0, SeekOrigin::Current).unwrap(), 1);
    assert_eq!(
        copy_file_range(src, Some(&mut read_at), dst, Some(&mut write_at), 64).unwrap(),
        0
    );
    assert_eq!((read_at, write_at), (8, 7));

    read_at = 0;
    assert_eq!(
        copy_file_range(src, Some(&mut read_at), dst, None, 2).unwrap(),
        2
    );
    assert_eq!(read_at, 2);
    assert_eq!(lseek(src, 0, SeekOrigin::Current).unwrap(), 2);
    assert_eq!(lseek(dst, 0, SeekOrigin::Current).unwrap(), 3);
    assert_eq!(copy_file_range(src, None, dst, None, 2).unwrap(), 2);
    assert_eq!(lseek(src, 0, SeekOrigin::Current).unwrap(), 4);
    assert_eq!(lseek(dst, 0, SeekOrigin::Current).unwrap(), 5);
    let readonly = File::open(&destination).unwrap();
    assert!(copy_file_range(
        src,
        Some(&mut read_at),
        readonly.as_fd(),
        Some(&mut write_at),
        1
    )
    .unwrap_err()
    .is_errno(EBADF));
    assert_eq!((read_at, write_at), (2, 7));
    assert_eq!(fs::read(&source).unwrap(), b"abcdefgh");
    assert_eq!(fs::read(&destination).unwrap(), b".abcdgh.");
}
