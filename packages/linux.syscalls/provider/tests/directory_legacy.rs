use linux_syscalls_provider::*;
use std::collections::BTreeMap;
use std::ffi::{CString, OsStr};
use std::fs::{self, File};
use std::os::fd::AsFd;
use std::os::unix::{ffi::OsStrExt, fs::symlink, fs::FileTypeExt, fs::MetadataExt};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

const EEXIST: i32 = 17;
const ENOTDIR: i32 = 20;

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
            "llmlang-directory-legacy-{}-{timestamp}-{number}",
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

fn c_path(path: &Path) -> CString {
    CString::new(path.as_os_str().as_bytes()).unwrap()
}

#[test]
fn native_fifo_modes_and_notifications_match_created_objects() {
    let scratch = Scratch::new();
    let directory = File::open(&scratch.0).unwrap();
    let dir = Directory::Borrowed(directory.as_fd());
    let absolute = scratch.0.join("absolute");
    let relative = scratch.0.join("relative");
    let instance = inotify_init1(InotifyMode::NonBlocking).unwrap();
    let watch = inotify_add_watch(&instance, &c_path(&scratch.0), WatchMask::CREATE).unwrap();
    mknod(&c_path(&absolute), 0).unwrap();
    mknodat(dir, c"relative", 0o640).unwrap();
    assert!(mknodat(dir, c"relative", 0o640)
        .unwrap_err()
        .is_errno(EEXIST));
    assert!(matches!(
        mknodat(dir, c"invalid", 0o20000),
        Err(SyscallError::InvalidInput(_))
    ));
    assert!(!scratch.0.join("invalid").exists());

    let absolute_meta = fs::symlink_metadata(&absolute).unwrap();
    let relative_meta = fs::symlink_metadata(&relative).unwrap();
    assert!(absolute_meta.file_type().is_fifo());
    assert!(relative_meta.file_type().is_fifo());
    assert_eq!(absolute_meta.mode() & 0o777, 0);
    assert_eq!(relative_meta.mode() & 0o777 & !0o640, 0);
    let mut buffer = [0; 1024];
    let events = read_inotify_events(&instance, &mut buffer).unwrap();
    let created: Vec<_> = events
        .iter()
        .map(|event| (event.descriptor, event.mask, event.name.unwrap().to_bytes()))
        .collect();
    assert_eq!(
        created,
        [
            (
                watch.descriptor(),
                WatchMask::CREATE.bits(),
                &b"absolute"[..]
            ),
            (
                watch.descriptor(),
                WatchMask::CREATE.bits(),
                &b"relative"[..]
            ),
        ]
    );
    inotify_rm_watch(watch).unwrap();

    let alias = scratch.0.join("alias");
    symlink("relative", &alias).unwrap();
    let original_link_mode = fs::symlink_metadata(&alias).unwrap().mode();
    fchmodat(dir, c"alias", 0o600).unwrap();
    assert!(fchmodat(dir, c"missing", 0o600).is_err());
    assert_eq!(
        fs::symlink_metadata(&alias).unwrap().mode(),
        original_link_mode
    );
    assert_eq!(
        fs::symlink_metadata(&relative).unwrap().mode() & 0o777,
        0o600
    );
    let reader = openat(
        dir,
        c"relative",
        OpenOptions {
            flags: O_RDONLY | O_NONBLOCK,
            mode: 0,
        },
    )
    .unwrap();
    let writer = openat(
        dir,
        c"relative",
        OpenOptions {
            flags: O_WRONLY | O_NONBLOCK,
            mode: 0,
        },
    )
    .unwrap();
    assert_eq!(write(writer.borrow(), b"fifo").unwrap(), 4);
    close(writer).unwrap();
    let mut data = [0xff; 5];
    assert_eq!(
        read(reader.borrow(), &mut data).unwrap(),
        ReadOutcome::Progress(4)
    );
    assert_eq!(&data, b"fifo\xff");
    assert_eq!(read(reader.borrow(), &mut data).unwrap(), ReadOutcome::Eof);
    close(reader).unwrap();
}

#[test]
fn native_legacy_directory_records_agree_with_modern_listing() {
    let scratch = Scratch::new();
    let binary_name = OsStr::from_bytes(b"file-\xff");
    fs::write(scratch.0.join(binary_name), b"data").unwrap();
    fs::create_dir(scratch.0.join("directory")).unwrap();
    symlink("directory", scratch.0.join("symlink")).unwrap();
    mknod(&c_path(&scratch.0.join("fifo")), 0o600).unwrap();
    let legacy = File::open(&scratch.0).unwrap();
    let modern = File::open(&scratch.0).unwrap();
    let regular = File::open(scratch.0.join(binary_name)).unwrap();
    let mut legacy_buffer = [0xff; 4096];
    let mut modern_buffer = [0xff; 4096];
    assert!(getdents(legacy.as_fd(), &mut [0; 16])
        .unwrap_err()
        .is_errno(EINVAL));
    assert!(getdents(regular.as_fd(), &mut legacy_buffer)
        .unwrap_err()
        .is_errno(ENOTDIR));
    let old_records = getdents(legacy.as_fd(), &mut legacy_buffer).unwrap();
    let new_records = getdents64(modern.as_fd(), &mut modern_buffer).unwrap();
    let legacy_set: BTreeMap<_, _> = old_records
        .iter()
        .map(|entry| (entry.name.to_bytes(), (entry.inode, entry.kind)))
        .collect();
    let modern_set: BTreeMap<_, _> = new_records
        .iter()
        .map(|entry| (entry.name.to_bytes(), (entry.inode, entry.kind)))
        .collect();
    assert_eq!(legacy_set, modern_set);
    assert!(legacy_set.contains_key(b".".as_slice()));
    assert!(legacy_set.contains_key(b"..".as_slice()));
    assert!(legacy_set.contains_key(binary_name.as_bytes()));
    assert!(matches!(legacy_set[b"fifo".as_slice()].1, 0 | 1));
    assert_eq!(
        legacy_set[b"fifo".as_slice()].0,
        fs::symlink_metadata(scratch.0.join("fifo")).unwrap().ino()
    );
    assert!(getdents(legacy.as_fd(), &mut legacy_buffer)
        .unwrap()
        .is_empty());
    assert!(getdents64(modern.as_fd(), &mut modern_buffer)
        .unwrap()
        .is_empty());
}
