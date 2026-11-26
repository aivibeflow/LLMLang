use linux_syscalls_provider::*;
use std::ffi::CString;
use std::fs::{self, File, Metadata};
use std::os::fd::AsFd;
use std::os::unix::{ffi::OsStrExt, fs::symlink, fs::MetadataExt};
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

const ENOENT: i32 = 2;

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
            "llmlang-metadata-{}-{timestamp}-{number}",
            std::process::id()
        ));
        fs::create_dir(&path).unwrap();
        Self(path)
    }

    fn c_path(&self, component: &str) -> CString {
        CString::new(self.0.join(component).as_os_str().as_bytes()).unwrap()
    }
}

impl Drop for Scratch {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

#[test]
fn native_ownership_updates_target_exact_objects_and_guard_sentinel() {
    let scratch = Scratch::new();
    let owner = geteuid().unwrap();
    let group = getegid().unwrap();
    let path = scratch.c_path("file");
    let link = scratch.c_path("link");
    let missing = scratch.c_path("missing");
    let file = File::create(scratch.0.join("file")).unwrap();
    symlink("missing", scratch.0.join("link")).unwrap();
    let directory = File::open(&scratch.0).unwrap();
    let dir = Directory::Borrowed(directory.as_fd());

    chown(&path, Some(owner), Some(group)).unwrap();
    assert!(chown(&link, None, None).unwrap_err().is_errno(ENOENT));
    lchown(&link, Some(owner), None).unwrap();
    fchownat(dir, c"link", None, Some(group), AT_SYMLINK_NOFOLLOW).unwrap();
    let link_metadata = fs::symlink_metadata(scratch.0.join("link")).unwrap();
    assert_eq!((link_metadata.uid(), link_metadata.gid()), (owner, group));
    assert!(matches!(
        chown(&missing, Some(u32::MAX), None),
        Err(SyscallError::InvalidInput(_))
    ));
    assert!(matches!(
        fchownat(dir, c"missing", None, Some(u32::MAX), 0),
        Err(SyscallError::InvalidInput(_))
    ));

    fs::remove_file(scratch.0.join("file")).unwrap();
    fchown(file.as_fd(), Some(owner), None).unwrap();
    fchownat(
        Directory::Borrowed(file.as_fd()),
        c"",
        None,
        Some(group),
        AT_EMPTY_PATH,
    )
    .unwrap();
    let metadata = file.metadata().unwrap();
    assert_eq!(
        (metadata.uid(), metadata.gid(), metadata.nlink()),
        (owner, group, 0)
    );
}

fn times(metadata: Metadata) -> ((i64, i64), (i64, i64)) {
    (
        (metadata.atime(), metadata.atime_nsec()),
        (metadata.mtime(), metadata.mtime_nsec()),
    )
}

fn epoch_seconds() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs() as i64
}

#[test]
fn native_second_and_microsecond_time_updates_match_kernel_metadata() {
    let scratch = Scratch::new();
    fs::write(scratch.0.join("file"), b"time").unwrap();
    let path = scratch.c_path("file");
    let directory = File::open(&scratch.0).unwrap();
    let dir = Directory::Borrowed(directory.as_fd());
    let read_times = || times(fs::metadata(scratch.0.join("file")).unwrap());
    const FIRST: i64 = 1_700_000_000;
    const SECOND: i64 = 1_700_000_123;
    utime(
        &path,
        Some(FileTimes {
            accessed: FIRST,
            modified: SECOND,
        }),
    )
    .unwrap();
    assert_eq!(read_times(), ((FIRST, 0), (SECOND, 0)));
    assert!(MicroTimestamp::new(FIRST, 1_000_000).is_err());
    let atime = MicroTimestamp::new(SECOND, 123_456).unwrap();
    let mtime = MicroTimestamp::new(FIRST, 999_999).unwrap();
    utimes(
        &path,
        Some(FileTimes {
            accessed: atime,
            modified: mtime,
        }),
    )
    .unwrap();
    assert_eq!(read_times(), ((SECOND, 123_456_000), (FIRST, 999_999_000)));
    futimesat(
        dir,
        c"file",
        Some(FileTimes {
            accessed: mtime,
            modified: atime,
        }),
    )
    .unwrap();
    assert_eq!(read_times(), ((FIRST, 999_999_000), (SECOND, 123_456_000)));
    assert!(futimesat(dir, c"missing", None)
        .unwrap_err()
        .is_errno(ENOENT));
    let before = epoch_seconds();
    utime(&path, None).unwrap();
    let ((access_seconds, _), (modify_seconds, _)) = read_times();
    let after = epoch_seconds();
    assert!((before - 1..=after + 1).contains(&access_seconds));
    assert!((before - 1..=after + 1).contains(&modify_seconds));
    assert_eq!(fs::read(scratch.0.join("file")).unwrap(), b"time");
}

#[test]
fn native_nanosecond_updates_cover_omit_now_and_nofollow() {
    let scratch = Scratch::new();
    let file = File::create(scratch.0.join("file")).unwrap();
    symlink("file", scratch.0.join("link")).unwrap();
    let directory = File::open(&scratch.0).unwrap();
    let dir = Directory::Borrowed(directory.as_fd());
    let atime = NanoTimestamp::exact(1_700_000_000, 123_456_789).unwrap();
    let mtime = NanoTimestamp::exact(1_700_000_123, 999_999_999).unwrap();
    assert!(NanoTimestamp::exact(1_700_000_000, 1_000_000_000).is_err());
    let pair = FileTimes {
        accessed: atime,
        modified: mtime,
    };
    utimensat(
        Directory::Borrowed(file.as_fd()),
        c"",
        Some(pair),
        AT_EMPTY_PATH,
    )
    .unwrap();
    let expected = ((1_700_000_000, 123_456_789), (1_700_000_123, 999_999_999));
    assert_eq!(times(file.metadata().unwrap()), expected);
    let reversed = FileTimes {
        accessed: mtime,
        modified: atime,
    };
    utimensat(dir, c"link", Some(reversed), AT_SYMLINK_NOFOLLOW).unwrap();
    assert_eq!(
        times(fs::symlink_metadata(scratch.0.join("link")).unwrap()),
        (expected.1, expected.0)
    );
    assert_eq!(times(file.metadata().unwrap()), expected);
    assert!(utimensat(dir, c"file", Some(pair), i32::MAX)
        .unwrap_err()
        .is_errno(EINVAL));
    let omit = FileTimes {
        accessed: NanoTimestamp::OMIT,
        modified: NanoTimestamp::OMIT,
    };
    utimensat(dir, c"missing", Some(omit), 0).unwrap();

    let before = epoch_seconds();
    let now = FileTimes {
        accessed: NanoTimestamp::OMIT,
        modified: NanoTimestamp::NOW,
    };
    utimensat(dir, c"link", Some(now), 0).unwrap();
    let (access_time, (modify_seconds, _)) = times(file.metadata().unwrap());
    let after = epoch_seconds();
    assert_eq!(access_time, expected.0);
    assert!((before - 1..=after + 1).contains(&modify_seconds));
}
