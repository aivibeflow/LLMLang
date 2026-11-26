use linux_syscalls_provider::*;
use std::ffi::CString;
use std::fs::{self, File, OpenOptions};
use std::os::fd::AsFd;
use std::os::unix::ffi::OsStrExt;
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
            "llmlang-files-extra2-{}-{timestamp}-{number}",
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
fn native_statfs_path_and_fd_observe_same_filesystem() {
    let scratch = Scratch::new();
    let path = scratch.0.join("file");
    let file = File::create(&path).unwrap();
    let directory = File::open(&scratch.0).unwrap();
    let path_info = statfs(&scratch.c_path("file")).unwrap();
    let file_info = fstatfs(file.as_fd()).unwrap();
    let directory_info = fstatfs(directory.as_fd()).unwrap();
    for fd_info in [file_info, directory_info] {
        assert_eq!(fd_info.filesystem_id, path_info.filesystem_id);
        assert_eq!(fd_info.fs_type, path_info.fs_type);
        assert_eq!(fd_info.block_size, path_info.block_size);
        assert_eq!(fd_info.fragment_size, path_info.fragment_size);
        assert_eq!(fd_info.name_length, path_info.name_length);
        assert_eq!(fd_info.flags, path_info.flags);
    }
    assert!(path_info.block_size > 0);
    assert!(path_info.fragment_size > 0);
    assert!(path_info.name_length >= 4);
    assert!(path_info.blocks > 0);
    fs::remove_file(&path).unwrap();
    assert!(statfs(&scratch.c_path("file"))
        .unwrap_err()
        .is_errno(ENOENT));
    assert_eq!(
        fstatfs(file.as_fd()).unwrap().filesystem_id,
        file_info.filesystem_id
    );
}

#[test]
fn native_sendfile_preserves_explicit_position_and_partial_progress() {
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
    let input = input.as_fd();
    let output = output.as_fd();
    lseek(input, 2, SeekOrigin::Start).unwrap();
    lseek(output, 1, SeekOrigin::Start).unwrap();
    let mut position = 5;
    assert_eq!(sendfile(output, input, Some(&mut position), 64).unwrap(), 3);
    assert_eq!(position, 8);
    assert_eq!(lseek(input, 0, SeekOrigin::Current).unwrap(), 2);
    assert_eq!(lseek(output, 0, SeekOrigin::Current).unwrap(), 4);
    assert_eq!(fs::read(&destination).unwrap(), b".fgh....");

    assert_eq!(sendfile(output, input, Some(&mut position), 64).unwrap(), 0);
    assert_eq!(position, 8);
    assert_eq!(lseek(output, 0, SeekOrigin::Current).unwrap(), 4);
    assert_eq!(sendfile(output, input, None, 2).unwrap(), 2);
    assert_eq!(lseek(input, 0, SeekOrigin::Current).unwrap(), 4);
    assert_eq!(lseek(output, 0, SeekOrigin::Current).unwrap(), 6);
    assert_eq!(fs::read(&destination).unwrap(), b".fghcd..");
    assert_eq!(fs::read(&source).unwrap(), b"abcdefgh");

    position = -1;
    assert!(sendfile(output, input, Some(&mut position), 1)
        .unwrap_err()
        .is_errno(EINVAL));
    assert_eq!(position, -1);
    position = 0;
    let readonly = File::open(&destination).unwrap();
    assert!(sendfile(readonly.as_fd(), input, Some(&mut position), 1)
        .unwrap_err()
        .is_errno(EBADF));
    assert_eq!(position, 0);
    assert_eq!(fs::read(&destination).unwrap(), b".fghcd..");
}

#[test]
fn native_memfd_starts_empty_and_owns_close_on_exec_descriptor() {
    let name = c"llmlang bytes";
    let first = memfd_create(name).unwrap();
    let second = memfd_create(name).unwrap();
    assert_eq!(fcntl_getfd(first.borrow()).unwrap() & 1, 1);
    assert_eq!(fcntl_getfd(second.borrow()).unwrap() & 1, 1);
    assert_eq!(fstat(first.borrow()).unwrap().size, 0);
    assert_eq!(read(first.borrow(), &mut [0]).unwrap(), ReadOutcome::Eof);
    assert_eq!(write(first.borrow(), b"a\0b").unwrap(), 3);
    assert_eq!(fstat(first.borrow()).unwrap().size, 3);
    assert_eq!(fstat(second.borrow()).unwrap().size, 0);
    let mut bytes = [0xff; 4];
    assert_eq!(
        pread64(first.borrow(), &mut bytes, 0).unwrap(),
        ReadOutcome::Progress(3)
    );
    assert_eq!(&bytes, b"a\0b\xff");
    close(first).unwrap();
    assert_eq!(read(second.borrow(), &mut [0]).unwrap(), ReadOutcome::Eof);
    close(second).unwrap();

    let too_long = CString::new(vec![b'x'; 256]).unwrap();
    assert!(memfd_create(&too_long).unwrap_err().is_errno(EINVAL));
}
