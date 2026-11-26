use linux_syscalls_provider::*;
use std::ffi::CString;
use std::fs::{self, File};
use std::io::{IoSlice, IoSliceMut};
use std::net::{Ipv4Addr, SocketAddrV4};
use std::os::fd::{AsFd, AsRawFd};
use std::time::{SystemTime, UNIX_EPOCH};

#[test]
fn read_write_distinguish_partial_progress_zero_eof_and_kernel_errno() {
    let (reader, writer) = pipe2(O_NONBLOCK).unwrap();
    let mut buffer = [0xff; 5];
    assert_eq!(
        read(reader.borrow(), &mut []).unwrap(),
        ReadOutcome::Progress(0)
    );
    assert_eq!(write(writer.borrow(), &[]).unwrap(), 0);
    assert!(read(reader.borrow(), &mut buffer)
        .unwrap_err()
        .is_errno(EAGAIN));
    assert!(read(writer.borrow(), &mut buffer)
        .unwrap_err()
        .is_errno(EBADF));
    assert!(write(reader.borrow(), b"x").unwrap_err().is_errno(EBADF));
    assert_eq!(write(writer.borrow(), b"abc").unwrap(), 3);
    assert_eq!(
        read(reader.borrow(), &mut buffer).unwrap(),
        ReadOutcome::Progress(3)
    );
    assert_eq!(&buffer, &[b'a', b'b', b'c', 0xff, 0xff]);
    close(writer).unwrap();
    assert_eq!(
        read(reader.borrow(), &mut buffer).unwrap(),
        ReadOutcome::Eof
    );
    close(reader).unwrap();
}

#[test]
fn nonblocking_pipe_exposes_partial_write_and_exact_prefix() {
    let (reader, writer) = pipe2(O_NONBLOCK).unwrap();
    let payload: Vec<u8> = (0..1_048_576).map(|index| (index % 251) as u8).collect();
    let progress = write(writer.borrow(), &payload).unwrap();
    assert!((1..payload.len()).contains(&progress));
    assert!(write(writer.borrow(), b"x").unwrap_err().is_errno(EAGAIN));
    close(writer).unwrap();
    let mut received = vec![0xff; progress + 1];
    assert_eq!(
        read(reader.borrow(), &mut received).unwrap(),
        ReadOutcome::Progress(progress)
    );
    assert_eq!(&received[..progress], &payload[..progress]);
    assert_eq!(received[progress], 0xff);
    assert_eq!(
        read(reader.borrow(), &mut received).unwrap(),
        ReadOutcome::Eof
    );
}

#[test]
fn read_reports_linux_eintr_without_implicit_retry() {
    use std::os::unix::thread::JoinHandleExt;
    use std::process::Command;
    use std::sync::mpsc;
    use std::thread;
    use std::time::Duration;

    const TEST_NAME: &str = "read_reports_linux_eintr_without_implicit_retry";
    const CHILD: &str = "LLMLANG_SYSCALL_EINTR_CHILD";
    if std::env::var_os(CHILD).is_none() {
        // Isolate the process-wide signal disposition from other tests.
        let output = Command::new(std::env::current_exe().unwrap())
            .args(["--exact", TEST_NAME, "--nocapture"])
            .env(CHILD, "1")
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "isolated signal test failed: {} {}",
            String::from_utf8_lossy(&output.stdout),
            String::from_utf8_lossy(&output.stderr)
        );
        return;
    }

    const SIGUSR1: i32 = 10;
    unsafe extern "C" {
        fn signal(number: i32, disposition: usize) -> usize;
        fn siginterrupt(number: i32, interrupt: i32) -> i32;
        fn pthread_kill(thread: std::ffi::c_ulong, number: i32) -> i32;
    }
    extern "C" fn handler(_: i32) {}
    // These test-only libc calls prepare a targeted, non-restarting signal.
    unsafe {
        assert_ne!(signal(SIGUSR1, handler as usize), usize::MAX);
        assert_eq!(siginterrupt(SIGUSR1, 1), 0);
    }
    let (reader, writer) = pipe2(0).unwrap();
    let (started, ready) = mpsc::channel();
    let (done, result) = mpsc::channel();
    let worker = thread::spawn(move || {
        let mut buffer = [0; 1];
        started.send(()).unwrap();
        done.send(read(reader.borrow(), &mut buffer)).unwrap();
    });
    ready.recv().unwrap();
    let mut interrupted = None;
    for _ in 0..100 {
        let delivered = unsafe { pthread_kill(worker.as_pthread_t(), SIGUSR1) };
        assert!(delivered == 0 || (delivered == 3 && worker.is_finished()));
        if let Ok(value) = result.recv_timeout(Duration::from_millis(5)) {
            interrupted = Some(value);
            break;
        }
    }
    // Make the read complete even if a regression silently retries EINTR.
    close(writer).unwrap();
    worker.join().unwrap();
    assert!(interrupted
        .expect("read timed out after targeted signals")
        .unwrap_err()
        .is_errno(EINTR));
}

#[test]
fn poll_preserves_readiness_and_timeout_observations() {
    let (reader, writer) = pipe2(0).unwrap();
    let mut watched = [PollEntry::new(reader.borrow(), POLLIN)];
    assert_eq!(poll(&mut watched, 0).unwrap(), 0);
    assert_eq!(watched[0].returned(), 0);
    assert_eq!(write(writer.borrow(), b"x").unwrap(), 1);
    assert_eq!(poll(&mut watched, 1000).unwrap(), 1);
    assert_eq!(watched[0].returned() & POLLIN, POLLIN);
    assert_eq!(
        read(reader.borrow(), &mut [0]).unwrap(),
        ReadOutcome::Progress(1)
    );
    assert_eq!(poll(&mut watched, 1).unwrap(), 0);
    let time = clock_gettime(CLOCK_MONOTONIC).unwrap();
    assert!(time.seconds() >= 0);
    assert!((0..1_000_000_000).contains(&time.nanos()));
    assert!(clock_gettime(i32::MAX).unwrap_err().is_errno(EINVAL));
}

struct Scratch(std::path::PathBuf);

impl Scratch {
    fn new() -> Self {
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let path = std::env::temp_dir().join(format!(
            "llmlang-provider-{}-{timestamp}",
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
fn positioned_and_vector_io_use_target_abi_and_preserve_file_offset() {
    let scratch = Scratch::new();
    let directory = File::open(&scratch.0).unwrap();
    let scope = Directory::Borrowed(directory.as_fd());
    let fd = openat(
        scope,
        c"file",
        OpenOptions {
            flags: O_CREAT | O_EXCL | O_RDWR,
            mode: 0o600,
        },
    )
    .unwrap();
    assert!(openat(
        scope,
        c"file",
        OpenOptions {
            flags: O_CREAT | O_EXCL | O_RDWR,
            mode: 0o600
        }
    )
    .is_err());
    assert_eq!(pwrite64(fd.borrow(), b"cde", 2).unwrap(), 3);
    assert_eq!(
        writev(fd.borrow(), &[IoSlice::new(b"a"), IoSlice::new(b"b")]).unwrap(),
        2
    );
    let mut chunk = [0; 3];
    assert_eq!(
        pread64(fd.borrow(), &mut chunk, 1).unwrap(),
        ReadOutcome::Progress(3)
    );
    assert_eq!(&chunk, b"bcd");
    let mut first = [0; 2];
    let mut second = [0x7f; 2];
    let mut vectors = [IoSliceMut::new(&mut first), IoSliceMut::new(&mut second)];
    assert_eq!(
        readv(fd.borrow(), &mut vectors).unwrap(),
        ReadOutcome::Progress(3)
    );
    assert_eq!(&first, b"cd");
    assert_eq!(second, [b'e', 0x7f]);
    assert_eq!(read(fd.borrow(), &mut chunk).unwrap(), ReadOutcome::Eof);
    fsync(fd.borrow()).unwrap();
    fdatasync(fd.borrow()).unwrap();
    syncfs(fd.borrow()).unwrap();
    close(fd).unwrap();
    assert_eq!(fs::read(scratch.0.join("file")).unwrap(), b"abcde");

    mkdirat(scope, c"dir", 0o700).unwrap();
    linkat(scope, c"file", scope, c"hard", 0).unwrap();
    renameat(scope, c"hard", scope, c"second").unwrap();
    symlinkat(c"second", scope, c"symbolic").unwrap();
    let mut dest = [0xff; 10];
    assert_eq!(readlinkat(scope, c"symbolic", &mut dest).unwrap(), 6);
    assert_eq!(&dest[..6], b"second");
    assert_eq!(dest[6], 0xff);
    unlinkat(scope, c"dir", AT_REMOVEDIR).unwrap();
    let missing = CString::new("missing").unwrap();
    assert!(readlinkat(scope, &missing, &mut dest).is_err());
}

#[test]
fn file_ownership_locks_permissions_and_metadata_follow_kernel_state() {
    let scratch = Scratch::new();
    let directory = File::open(&scratch.0).unwrap();
    let scope = Directory::Borrowed(directory.as_fd());
    let mode = OpenOptions {
        flags: O_CREAT | O_EXCL | O_RDWR,
        mode: 0o600,
    };
    let file = openat(scope, c"state", mode).unwrap();
    assert_eq!(fcntl_getfd(file.borrow()).unwrap() & 1, 1);
    assert_eq!(write(file.borrow(), b"state").unwrap(), 5);
    assert_eq!(lseek(file.borrow(), 1, SeekOrigin::Start).unwrap(), 1);
    let duplicate = dup(file.borrow()).unwrap();
    let cloexec = dup_cloexec(file.borrow(), 0).unwrap();
    assert_eq!(fcntl_getfd(duplicate.borrow()).unwrap() & 1, 0);
    assert_eq!(fcntl_getfd(cloexec.borrow()).unwrap() & 1, 1);
    let mut next = [0; 1];
    assert_eq!(
        read(duplicate.borrow(), &mut next).unwrap(),
        ReadOutcome::Progress(1)
    );
    assert_eq!(&next, b"t");
    assert_eq!(lseek(file.borrow(), 0, SeekOrigin::Current).unwrap(), 2);
    close(duplicate).unwrap();
    close(cloexec).unwrap();

    let independent = openat(
        scope,
        c"state",
        OpenOptions {
            flags: O_RDWR,
            mode: 0,
        },
    )
    .unwrap();
    flock(file.borrow(), LOCK_EX | LOCK_NB).unwrap();
    assert!(flock(independent.borrow(), LOCK_EX | LOCK_NB)
        .unwrap_err()
        .is_errno(EAGAIN));
    flock(file.borrow(), LOCK_UN).unwrap();
    flock(independent.borrow(), LOCK_EX | LOCK_NB).unwrap();
    close(independent).unwrap();

    ftruncate(file.borrow(), 3).unwrap();
    assert_eq!(statx(scope, c"state", 0).unwrap().size, Some(3));
    fchmod(file.borrow(), 0o640).unwrap();
    assert_eq!(
        statx(Directory::Borrowed(file.borrow()), c"", AT_EMPTY_PATH)
            .unwrap()
            .permissions,
        Some(0o640)
    );
    fchmodat2(scope, c"state", 0o600, 0).unwrap();
    assert_eq!(statx(scope, c"state", 0).unwrap().permissions, Some(0o600));
    assert!(faccessat2(scope, c"state", 0, AT_EACCESS).is_ok());
    assert!(faccessat2(scope, c"missing", 0, AT_EACCESS).is_err());

    let listing = openat(
        scope,
        c".",
        OpenOptions {
            flags: O_RDONLY | O_DIRECTORY,
            mode: 0,
        },
    )
    .unwrap();
    let mut dirents = [0; 4096];
    let batch = getdents64(listing.borrow(), &mut dirents).unwrap();
    let found = batch.iter().find(|entry| entry.name == c"state").unwrap();
    assert_eq!(Some(found.inode), statx(scope, c"state", 0).unwrap().inode);
    assert!(getdents64(listing.borrow(), &mut dirents)
        .unwrap()
        .is_empty());
    assert!(getdents64(file.borrow(), &mut dirents).is_err());
}

fn child_status(program: &std::ffi::CStr, args: &[&std::ffi::CStr]) -> WaitStatus {
    let image = ExecImage::new(program, args, &[]).unwrap();
    let mut child = fork_execve(&image).unwrap();
    loop {
        match wait4(&mut child, 0) {
            Ok(Some(status)) => {
                assert!(child.pid().is_none());
                assert!(wait4(&mut child, 0).is_err());
                return status;
            }
            Err(error) if error.is_errno(EINTR) => continue,
            unexpected => panic!("unexpected wait4 result: {unexpected:?}"),
        }
    }
}

#[test]
fn fork_exec_wait_distinguishes_exit_and_failed_exec() {
    assert_eq!(getpid().unwrap(), std::process::id() as i32);
    assert!(ExecImage::new(c"/bin/sh", &[], &[]).is_err());
    assert_eq!(
        child_status(c"/bin/sh", &[c"sh", c"-c", c"exit 37"]).exited(),
        Some(37)
    );
    assert_eq!(
        child_status(c"/dev/null/missing", &[c"missing"]).exited(),
        Some(127)
    );
    let invalid = ExecImage::new(c"/dev/null/missing", &[c"missing"], &[]).unwrap();
    assert!(execve(&invalid).is_err());
}

#[test]
fn ipv4_tcp_loopback_exchanges_exact_bytes_and_reports_peer_addresses() {
    let listener = socket().unwrap();
    bind(listener.borrow(), SocketAddrV4::new(Ipv4Addr::LOCALHOST, 0)).unwrap();
    listen(listener.borrow(), 1).unwrap();
    let server_address = getsockname(listener.borrow()).unwrap();
    assert_eq!(*server_address.ip(), Ipv4Addr::LOCALHOST);
    assert_ne!(server_address.port(), 0);
    let client = socket().unwrap();
    connect(client.borrow(), server_address).unwrap();
    let connection = accept(listener.borrow()).unwrap();
    assert_eq!(fcntl_getfd(connection.borrow()).unwrap() & 1, 0);
    assert_eq!(getpeername(client.borrow()).unwrap(), server_address);
    assert_eq!(
        getpeername(connection.borrow()).unwrap(),
        getsockname(client.borrow()).unwrap()
    );
    assert_eq!(sendto(client.borrow(), b"ping!").unwrap(), 5);
    shutdown(client.borrow(), Shutdown::Write).unwrap();
    let mut buffer = [0; 5];
    let mut received = 0;
    while received < buffer.len() {
        let ReadOutcome::Progress(count) =
            recvfrom(connection.borrow(), &mut buffer[received..]).unwrap()
        else {
            panic!("unexpected early TCP EOF");
        };
        received += count;
    }
    assert_eq!(&buffer, b"ping!");
    assert_eq!(
        recvfrom(connection.borrow(), &mut buffer).unwrap(),
        ReadOutcome::Eof
    );
    close(connection).unwrap();
    close(client).unwrap();
    let second_client = socket().unwrap();
    connect(second_client.borrow(), server_address).unwrap();
    let second_connection = accept4(listener.borrow()).unwrap();
    assert_eq!(fcntl_getfd(second_connection.borrow()).unwrap() & 1, 1);
    close(second_connection).unwrap();
    close(second_client).unwrap();
    close(listener).unwrap();
}

#[test]
fn exec_inherits_only_descriptors_without_cloexec() {
    let (inherited, inherited_writer) = pipe().unwrap();
    let (closed, closed_writer) = pipe2(O_CLOEXEC).unwrap();
    let inherited_path = format!("/proc/self/fd/{}", inherited.borrow().as_raw_fd());
    let closed_path = format!("/proc/self/fd/{}", closed.borrow().as_raw_fd());
    // Both descriptors exist in the parent, and the pipe identities differ.
    let inherited_identity = fs::read_link(&inherited_path).unwrap();
    let closed_identity = fs::read_link(&closed_path).unwrap();
    assert_ne!(inherited_identity, closed_identity);

    let command = CString::new(format!(
        "test -p '{inherited_path}' && test ! -e '{closed_path}'"
    ))
    .unwrap();
    let status = child_status(c"/bin/sh", &[c"sh", c"-c", &command]);
    assert_eq!(status.exited(), Some(0));
    assert_eq!(fs::read_link(&inherited_path).unwrap(), inherited_identity);
    assert_eq!(fs::read_link(&closed_path).unwrap(), closed_identity);
    for fd in [inherited, inherited_writer, closed, closed_writer] {
        close(fd).unwrap();
    }
}
