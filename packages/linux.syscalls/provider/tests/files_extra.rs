use linux_syscalls_provider::*;
use std::ffi::CString;
use std::fs::{self, File, Metadata};
use std::os::fd::AsFd;
use std::os::unix::{ffi::OsStrExt, fs::MetadataExt};
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

const ENOENT: i32 = 2;
const FILE_TYPE: u32 = 0o170000;
const SYMLINK_TYPE: u32 = 0o120000;
const REGULAR_FILE_TYPE: u32 = 0o100000;

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
            "llmlang-files-extra-{}-{timestamp}-{number}",
            std::process::id()
        ));
        fs::create_dir(&path).unwrap();
        Self(path)
    }

    fn path(&self, component: &str) -> CString {
        CString::new(self.0.join(component).as_os_str().as_bytes()).unwrap()
    }
}

impl Drop for Scratch {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

#[test]
fn native_open_create_truncate_access_and_mode() {
    let dir = Scratch::new();
    let path = dir.path("data");
    assert!(access(&path, 0).unwrap_err().is_errno(ENOENT));
    let file = creat(&path, 0o600).unwrap();
    assert_eq!(fcntl_getfd(file.borrow()).unwrap() & 1, 0);
    let marked = open(
        &path,
        OpenOptions {
            flags: O_RDONLY | O_CLOEXEC,
            mode: 0,
        },
    )
    .unwrap();
    assert_eq!(fcntl_getfd(marked.borrow()).unwrap() & 1, 1);
    close(marked).unwrap();
    assert_eq!(write(file.borrow(), b"abcde").unwrap(), 5);
    close(file).unwrap();
    assert_eq!(stat(&path).unwrap().size, 5);
    assert!(truncate(&path, -1).unwrap_err().is_errno(EINVAL));
    truncate(&path, 3).unwrap();
    chmod(&path, 0o640).unwrap();
    assert!(access(&path, 0).is_ok());
    assert_eq!(stat(&path).unwrap().mode & 0o777, 0o640);
    let file = open(
        &path,
        OpenOptions {
            flags: O_RDONLY,
            mode: 0,
        },
    )
    .unwrap();
    assert_eq!(fcntl_getfd(file.borrow()).unwrap() & 1, 0);
    let mut contents = [0xff; 4];
    assert_eq!(
        read(file.borrow(), &mut contents).unwrap(),
        ReadOutcome::Progress(3)
    );
    assert_eq!(&contents, b"abc\xff");
    close(file).unwrap();

    let file = creat(&path, 0o600).unwrap();
    assert_eq!(fstat(file.borrow()).unwrap().size, 0);
    close(file).unwrap();
    let missing = dir.path("missing");
    assert!(open(
        &missing,
        OpenOptions {
            flags: O_RDONLY,
            mode: 0
        }
    )
    .unwrap_err()
    .is_errno(ENOENT));
}

#[test]
fn native_path_mutations_preserve_link_and_directory_semantics() {
    let dir = Scratch::new();
    let subdir = dir.path("subdir");
    let source = dir.path("subdir/source");
    let alias = dir.path("subdir/alias");
    let renamed = dir.path("subdir/renamed");
    let symbolic = dir.path("subdir/symbolic");
    let symbolic_hardlink = dir.path("subdir/symbolic-hardlink");
    mkdir(&subdir, 0o700).unwrap();
    assert!(mkdir(&subdir, 0o700).is_err());
    close(creat(&source, 0o600).unwrap()).unwrap();
    assert!(rmdir(&subdir).is_err());
    link(&source, &alias).unwrap();
    assert_eq!(stat(&source).unwrap().links, 2);
    rename(&alias, &renamed).unwrap();
    assert!(stat(&alias).unwrap_err().is_errno(ENOENT));
    assert_eq!(stat(&source).unwrap().inode, stat(&renamed).unwrap().inode);

    symlink(c"renamed", &symbolic).unwrap();
    let mut link_bytes = [0xff; 9];
    assert_eq!(readlink(&symbolic, &mut link_bytes).unwrap(), 7);
    assert_eq!(&link_bytes, b"renamed\xff\xff");
    assert_eq!(readlink(&symbolic, &mut link_bytes[..3]).unwrap(), 3);
    assert_eq!(&link_bytes[..3], b"ren");
    assert!(readlink(&source, &mut link_bytes)
        .unwrap_err()
        .is_errno(EINVAL));
    assert_eq!(stat(&symbolic).unwrap().mode & FILE_TYPE, REGULAR_FILE_TYPE);
    assert_eq!(lstat(&symbolic).unwrap().mode & FILE_TYPE, SYMLINK_TYPE);

    link(&symbolic, &symbolic_hardlink).unwrap();
    assert_eq!(
        lstat(&symbolic_hardlink).unwrap().inode,
        lstat(&symbolic).unwrap().inode
    );
    unlink(&renamed).unwrap();
    assert!(stat(&symbolic).unwrap_err().is_errno(ENOENT));
    assert_eq!(lstat(&symbolic).unwrap().links, 2);
    unlink(&symbolic_hardlink).unwrap();
    unlink(&symbolic).unwrap();
    unlink(&source).unwrap();
    rmdir(&subdir).unwrap();
    assert!(lstat(&subdir).unwrap_err().is_errno(ENOENT));
}

fn check_independent_metadata(actual: FileStat, expected: Metadata) {
    assert_eq!(actual.device, expected.dev());
    assert_eq!(actual.inode, expected.ino());
    assert_eq!(actual.links, expected.nlink());
    assert_eq!(actual.mode, expected.mode());
    assert_eq!(actual.uid, expected.uid());
    assert_eq!(actual.gid, expected.gid());
    assert_eq!(actual.special_device, expected.rdev());
    assert_eq!(actual.size, expected.size() as i64);
    assert_eq!(actual.block_size, expected.blksize() as i64);
    assert_eq!(actual.blocks, expected.blocks() as i64);
    assert_eq!(actual.accessed.seconds(), expected.atime());
    assert_eq!(actual.accessed.nanos(), expected.atime_nsec() as u32);
    assert_eq!(actual.modified.seconds(), expected.mtime());
    assert_eq!(actual.modified.nanos(), expected.mtime_nsec() as u32);
    assert_eq!(actual.changed.seconds(), expected.ctime());
    assert_eq!(actual.changed.nanos(), expected.ctime_nsec() as u32);
}

#[test]
fn native_stat_variants_agree_with_independent_metadata() {
    let dir = Scratch::new();
    let file_path = dir.0.join("file");
    let symbolic_path = dir.0.join("symbolic");
    fs::write(&file_path, b"abc").unwrap();
    std::os::unix::fs::symlink("file", &symbolic_path).unwrap();
    let file = File::open(&file_path).unwrap();
    let directory = File::open(&dir.0).unwrap();
    let directory = Directory::Borrowed(directory.as_fd());
    let followed = stat(&dir.path("symbolic")).unwrap();
    assert_eq!(fstat(file.as_fd()).unwrap(), followed);
    assert_eq!(newfstatat(directory, c"symbolic", 0).unwrap(), followed);
    // Following a symlink can update its atime, including under relatime.
    let link = lstat(&dir.path("symbolic")).unwrap();
    assert_eq!(
        newfstatat(directory, c"symbolic", AT_SYMLINK_NOFOLLOW).unwrap(),
        link
    );
    assert_eq!(
        newfstatat(Directory::Borrowed(file.as_fd()), c"", AT_EMPTY_PATH).unwrap(),
        followed
    );
    assert!(newfstatat(directory, c"missing", 0)
        .unwrap_err()
        .is_errno(ENOENT));
    assert!(faccessat(directory, c"file", 0).is_ok());
    assert!(faccessat(directory, c"missing", 0)
        .unwrap_err()
        .is_errno(ENOENT));
    assert!(faccessat(directory, c"file", 8)
        .unwrap_err()
        .is_errno(EINVAL));
    check_independent_metadata(followed, fs::metadata(&file_path).unwrap());
    check_independent_metadata(link, fs::symlink_metadata(&symbolic_path).unwrap());
}
