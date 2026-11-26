use linux_syscalls_provider::*;
use std::fs::{self, File};
use std::os::fd::{AsFd, AsRawFd};
use std::os::unix::fs::symlink;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

#[test]
fn duplication_replaces_only_the_owned_target_descriptor() {
    let (source, source_writer) = pipe2(0).unwrap();
    let (target, other_writer) = pipe2(0).unwrap();
    let number = target.as_raw_fd();
    let replaced = dup2(source.borrow(), target).unwrap();
    assert_eq!(replaced.as_raw_fd(), number);
    assert_eq!(fcntl_getfd(replaced.borrow()).unwrap() & 1, 0);

    let (third_target, third_writer) = pipe2(0).unwrap();
    let third_number = third_target.as_raw_fd();
    let third = dup3(source.borrow(), third_target, true).unwrap();
    assert_eq!(third.as_raw_fd(), third_number);
    assert_eq!(fcntl_getfd(third.borrow()).unwrap() & 1, 1);
    close(other_writer).unwrap();
    close(third_writer).unwrap();
    write(source_writer.borrow(), b"xy").unwrap();
    let mut byte = [0];
    assert_eq!(
        read(replaced.borrow(), &mut byte).unwrap(),
        ReadOutcome::Progress(1)
    );
    assert_eq!(&byte, b"x");
    assert_eq!(
        read(third.borrow(), &mut byte).unwrap(),
        ReadOutcome::Progress(1)
    );
    assert_eq!(&byte, b"y");
    for fd in [source, source_writer, replaced, third] {
        close(fd).unwrap();
    }
}

#[test]
fn openat2_keeps_relative_resolution_beneath_the_borrowed_directory() {
    struct Scratch(PathBuf);
    impl Drop for Scratch {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }
    let stamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let scratch = Scratch(
        std::env::temp_dir().join(format!("llmlang-openat2-{}-{stamp}", std::process::id())),
    );
    fs::create_dir(&scratch.0).unwrap();
    fs::create_dir(scratch.0.join("scope")).unwrap();
    fs::write(scratch.0.join("scope/inside"), b"x").unwrap();
    fs::write(scratch.0.join("outside"), b"z").unwrap();
    symlink("../outside", scratch.0.join("scope/escape")).unwrap();
    let directory = File::open(scratch.0.join("scope")).unwrap();
    let options = OpenOptions {
        flags: O_RDONLY,
        mode: 0,
    };
    let file = openat2_beneath(directory.as_fd(), c"inside", options).unwrap();
    assert_eq!(fcntl_getfd(file.borrow()).unwrap() & 1, 1);
    let mut result = [0];
    assert_eq!(
        read(file.borrow(), &mut result).unwrap(),
        ReadOutcome::Progress(1)
    );
    assert_eq!(&result, b"x");
    assert!(openat2_beneath(directory.as_fd(), c"escape", options)
        .unwrap_err()
        .is_errno(18));
    assert!(openat2_beneath(directory.as_fd(), c"../outside", options)
        .unwrap_err()
        .is_errno(18));
    assert!(openat2_beneath(directory.as_fd(), c"missing", options)
        .unwrap_err()
        .is_errno(2));
    close(file).unwrap();
}

#[test]
fn duplication_error_preserves_owned_target() {
    const CHILD: &str = "LLMLANG_DUP_SLOT_CHILD";
    if std::env::var_os(CHILD).is_none() {
        let output = std::process::Command::new(std::env::current_exe().unwrap())
            .args(["--exact", "duplication_error_preserves_owned_target"])
            .env(CHILD, "1")
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "{}",
            String::from_utf8_lossy(&output.stdout)
        );
        return;
    }
    let (source, _) = pipe2(0).unwrap();
    let (target, target_writer) = pipe2(0).unwrap();
    let original = getrlimit(LimitResource::OpenFiles).unwrap();
    let number = target.as_raw_fd();
    setrlimit(
        LimitResource::OpenFiles,
        Rlimit {
            soft: Limit::Finite(number as u64),
            hard: original.hard,
        },
    )
    .unwrap();
    let (error, target) = dup2(source.borrow(), target).unwrap_err().into_parts();
    assert!(error.is_errno(EBADF));
    let (error, target) = dup3(source.borrow(), target, true)
        .unwrap_err()
        .into_parts();
    assert!(error.is_errno(EBADF));
    setrlimit(LimitResource::OpenFiles, original).unwrap();
    assert_eq!(target.as_raw_fd(), number);
    assert_eq!(write(target_writer.borrow(), b"z").unwrap(), 1);
    let mut byte = [0];
    assert_eq!(
        read(target.borrow(), &mut byte).unwrap(),
        ReadOutcome::Progress(1)
    );
    assert_eq!(&byte, b"z");
}
