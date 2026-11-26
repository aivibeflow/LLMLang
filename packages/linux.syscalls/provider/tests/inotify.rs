use linux_syscalls_provider::*;
use std::ffi::{CString, OsStr};
use std::fs;
use std::os::unix::ffi::OsStrExt;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

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
            "llmlang-inotify-{}-{timestamp}-{number}",
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
fn native_inotify_init_forms_preserve_descriptor_flags() {
    let legacy = inotify_init().unwrap();
    assert_eq!(fcntl_getfd(legacy.borrow()).unwrap() & 1, 0);
    assert_eq!(fcntl_getfl(legacy.borrow()).unwrap() & O_NONBLOCK, 0);
    close(legacy.into_fd()).unwrap();

    let blocking = inotify_init1(InotifyMode::Blocking).unwrap();
    assert_eq!(fcntl_getfd(blocking.borrow()).unwrap() & 1, 1);
    assert_eq!(fcntl_getfl(blocking.borrow()).unwrap() & O_NONBLOCK, 0);
    close(blocking.into_fd()).unwrap();

    let nonblocking = inotify_init1(InotifyMode::NonBlocking).unwrap();
    assert_eq!(fcntl_getfd(nonblocking.borrow()).unwrap() & 1, 1);
    assert_eq!(
        fcntl_getfl(nonblocking.borrow()).unwrap() & O_NONBLOCK,
        O_NONBLOCK
    );
    close(nonblocking.into_fd()).unwrap();
}

#[test]
fn native_nonblocking_watch_preserves_record_order_and_rename_cookie() {
    let scratch = Scratch::new();
    let directory = c_path(&scratch.0);
    let instance = inotify_init1(InotifyMode::NonBlocking).unwrap();
    let mask = WatchMask::CREATE
        .combine(WatchMask::MOVED_FROM)
        .combine(WatchMask::MOVED_TO)
        .combine(WatchMask::DELETE);
    let token = inotify_add_watch(&instance, &directory, mask).unwrap();
    let descriptor = token.descriptor();
    assert!(inotify_add_watch(&instance, &directory, WatchMask::ATTRIB)
        .unwrap_err()
        .is_errno(EEXIST));
    let mut buffer = [0_u8; 4096];
    assert!(read_inotify_events(&instance, &mut buffer)
        .unwrap_err()
        .is_errno(EAGAIN));
    let original = OsStr::from_bytes(b"created-\xff");
    let renamed = "renamed";
    fs::write(scratch.0.join(original), b"data").unwrap();
    fs::rename(scratch.0.join(original), scratch.0.join(renamed)).unwrap();
    fs::remove_file(scratch.0.join(renamed)).unwrap();
    assert!(read_inotify_events(&instance, &mut [0; 16])
        .unwrap_err()
        .is_errno(EINVAL));

    let events = read_inotify_events(&instance, &mut buffer).unwrap();
    assert_eq!(events.len(), 4);
    let observed: Vec<_> = events
        .iter()
        .map(|event| (event.descriptor, event.mask, event.name.unwrap().to_bytes()))
        .collect();
    assert_eq!(
        observed,
        [
            (descriptor, WatchMask::CREATE.bits(), original.as_bytes()),
            (
                descriptor,
                WatchMask::MOVED_FROM.bits(),
                original.as_bytes()
            ),
            (descriptor, WatchMask::MOVED_TO.bits(), renamed.as_bytes()),
            (descriptor, WatchMask::DELETE.bits(), renamed.as_bytes()),
        ]
    );
    assert_ne!(events[1].cookie, 0);
    assert_eq!(events[1].cookie, events[2].cookie);
    assert_eq!(events[0].cookie, 0);
    assert_eq!(events[3].cookie, 0);

    inotify_rm_watch(token).unwrap();
    let ignored = read_inotify_events(&instance, &mut buffer).unwrap();
    assert_eq!(
        ignored,
        [InotifyEvent {
            descriptor,
            mask: IN_IGNORED,
            cookie: 0,
            name: None
        }]
    );
    assert!(read_inotify_events(&instance, &mut buffer)
        .unwrap_err()
        .is_errno(EAGAIN));
    close(instance.into_fd()).unwrap();
}

#[test]
fn native_watch_token_drop_and_kernel_removal_do_not_reuse_ownership() {
    let scratch = Scratch::new();
    let directory = scratch.0.join("watched");
    fs::create_dir(&directory).unwrap();
    let path = c_path(&directory);
    let instance = inotify_init1(InotifyMode::NonBlocking).unwrap();
    let mut buffer = [0_u8; 4096];
    let first = inotify_add_watch(&instance, &path, WatchMask::DELETE_SELF).unwrap();
    let first_descriptor = first.descriptor();
    drop(first);
    assert_eq!(
        read_inotify_events(&instance, &mut buffer).unwrap(),
        [InotifyEvent {
            descriptor: first_descriptor,
            mask: IN_IGNORED,
            cookie: 0,
            name: None
        }]
    );

    let second = inotify_add_watch(&instance, &path, WatchMask::DELETE_SELF).unwrap();
    let second_descriptor = second.descriptor();
    fs::remove_dir(&directory).unwrap();
    let removed = read_inotify_events(&instance, &mut buffer).unwrap();
    assert_eq!(
        removed,
        [
            InotifyEvent {
                descriptor: second_descriptor,
                mask: WatchMask::DELETE_SELF.bits(),
                cookie: 0,
                name: None
            },
            InotifyEvent {
                descriptor: second_descriptor,
                mask: IN_IGNORED,
                cookie: 0,
                name: None
            },
        ]
    );
    assert!(inotify_rm_watch(second).unwrap_err().is_errno(EINVAL));
    assert!(read_inotify_events(&instance, &mut buffer)
        .unwrap_err()
        .is_errno(EAGAIN));
}
