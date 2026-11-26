use linux_syscalls_provider::*;
use std::ffi::CString;
use std::fs::{self, File};
use std::os::fd::AsFd;
use std::os::unix::{ffi::OsStrExt, fs::symlink};
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

const EEXIST: i32 = 17;
const ERANGE: i32 = 34;
const ENODATA: i32 = 61;

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
            "llmlang-xattr-{}-{timestamp}-{number}",
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
fn native_path_and_fd_values_size_copy_replace_remove() {
    let scratch = Scratch::new();
    let file = File::create(scratch.0.join("file")).unwrap();
    let path = scratch.c_path("file");
    let name = c"user.llmlang-value";
    let fd = file.as_fd();
    assert!(getxattr(&path, name, None).unwrap_err().is_errno(ENODATA));
    assert!(fsetxattr(fd, name, b"missing", XattrMode::Replace)
        .unwrap_err()
        .is_errno(ENODATA));
    setxattr(&path, name, b"first\0value", XattrMode::Create).unwrap();
    assert!(setxattr(&path, name, b"collision", XattrMode::Create)
        .unwrap_err()
        .is_errno(EEXIST));
    assert_eq!(getxattr(&path, name, None).unwrap(), 11);
    assert_eq!(fgetxattr(fd, name, Some(&mut [])).unwrap(), 11);
    assert!(fgetxattr(fd, name, Some(&mut [0; 10]))
        .unwrap_err()
        .is_errno(ERANGE));
    let mut buffer = [0xff; 14];
    assert_eq!(getxattr(&path, name, Some(&mut buffer)).unwrap(), 11);
    assert_eq!(&buffer, b"first\0value\xff\xff\xff");

    fsetxattr(fd, name, b"second", XattrMode::Replace).unwrap();
    assert_eq!(fgetxattr(fd, name, Some(&mut buffer)).unwrap(), 6);
    assert_eq!(&buffer[..6], b"second");
    fsetxattr(fd, name, b"", XattrMode::Upsert).unwrap();
    buffer.fill(0xff);
    assert_eq!(fgetxattr(fd, name, Some(&mut buffer)).unwrap(), 0);
    assert_eq!(fgetxattr(fd, name, None).unwrap(), 0);
    assert_eq!(buffer, [0xff; 14]);
    fremovexattr(fd, name).unwrap();
    assert!(fgetxattr(fd, name, None).unwrap_err().is_errno(ENODATA));
    assert!(fremovexattr(fd, name).unwrap_err().is_errno(ENODATA));
}

fn names(bytes: &[u8]) -> Vec<&[u8]> {
    if bytes.is_empty() {
        return Vec::new();
    }
    let (last, names) = bytes.split_last().unwrap();
    assert_eq!(*last, 0);
    let mut names: Vec<_> = names.split(|&byte| byte == 0).collect();
    assert!(names.iter().all(|name| !name.is_empty()));
    names.sort_unstable();
    names
}

#[test]
fn native_list_size_and_copy_preserve_name_boundaries() {
    let scratch = Scratch::new();
    let file = File::create(scratch.0.join("file")).unwrap();
    let fd = file.as_fd();
    let path = scratch.c_path("file");
    let first = c"user.llmlang-first";
    let second = c"user.llmlang-second";
    lsetxattr(&path, first, b"a", XattrMode::Upsert).unwrap();
    setxattr(&path, second, b"b", XattrMode::Upsert).unwrap();
    let len = listxattr(&path, None).unwrap();
    assert_eq!(flistxattr(fd, Some(&mut [])).unwrap(), len);
    assert!(listxattr(&path, Some(&mut [0; 1]))
        .unwrap_err()
        .is_errno(ERANGE));
    let mut by_path = vec![0xff; len + 1];
    assert_eq!(listxattr(&path, Some(&mut by_path)).unwrap(), len);
    assert_eq!(by_path[len], 0xff);
    let mut by_fd = vec![0xff; len + 1];
    assert_eq!(flistxattr(fd, Some(&mut by_fd)).unwrap(), len);
    assert_eq!(by_fd[len], 0xff);
    let listed = names(&by_path[..len]);
    assert_eq!(listed, names(&by_fd[..len]));
    assert!(listed.contains(&first.to_bytes()));
    assert!(listed.contains(&second.to_bytes()));
    lremovexattr(&path, first).unwrap();
    removexattr(&path, second).unwrap();
    assert!(lgetxattr(&path, first, None).unwrap_err().is_errno(ENODATA));
    assert!(getxattr(&path, second, None).unwrap_err().is_errno(ENODATA));
}

#[test]
fn native_follow_and_nofollow_forms_select_distinct_objects() {
    let scratch = Scratch::new();
    let file = File::create(scratch.0.join("file")).unwrap();
    symlink("file", scratch.0.join("link")).unwrap();
    let path = scratch.c_path("file");
    let link = scratch.c_path("link");
    let name = c"user.llmlang-link-check";
    setxattr(&link, name, b"target", XattrMode::Upsert).unwrap();
    assert_eq!(getxattr(&link, name, None).unwrap(), 6);
    let mut buffer = [0xff; 7];
    assert_eq!(lgetxattr(&path, name, Some(&mut buffer)).unwrap(), 6);
    assert_eq!(&buffer, b"target\xff");
    assert!(lgetxattr(&link, name, None).is_err());
    assert!(lsetxattr(&link, name, b"wrong-object", XattrMode::Upsert).is_err());
    assert!(lremovexattr(&link, name).is_err());
    assert_eq!(fgetxattr(file.as_fd(), name, None).unwrap(), 6);

    let len = llistxattr(&link, None).unwrap();
    let mut list = vec![0; len];
    assert_eq!(llistxattr(&link, Some(&mut list)).unwrap(), len);
    assert!(!names(&list).contains(&name.to_bytes()));
    let target_len = listxattr(&link, None).unwrap();
    list.resize(target_len, 0);
    assert_eq!(listxattr(&link, Some(&mut list)).unwrap(), target_len);
    assert!(names(&list).contains(&name.to_bytes()));
    removexattr(&link, name).unwrap();
    assert!(fgetxattr(file.as_fd(), name, None)
        .unwrap_err()
        .is_errno(ENODATA));
}
