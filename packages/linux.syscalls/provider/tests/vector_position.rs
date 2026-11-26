use linux_syscalls_provider::*;
use std::fs::{self, File, OpenOptions};
use std::io::{IoSlice, IoSliceMut};
use std::os::fd::AsFd;
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

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
            "llmlang-vector-position-{}-{timestamp}-{number}",
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
fn native_positioned_vectors_keep_full_offsets_and_partial_progress() {
    let scratch = Scratch::new();
    let path = scratch.0.join("sparse-file");
    fs::write(&path, b"old").unwrap();
    let file = OpenOptions::new()
        .read(true)
        .write(true)
        .open(&path)
        .unwrap();
    let fd = file.as_fd();
    assert_eq!(lseek(fd, 2, SeekOrigin::Start).unwrap(), 2);
    let source = [IoSlice::new(b"AB"), IoSlice::new(b"c")];
    const OFFSET: i64 = (1_i64 << 32) + 4096;
    assert!(pwritev(fd, &source, -1).unwrap_err().is_errno(EINVAL));
    assert_eq!(pwritev(fd, &source, OFFSET).unwrap(), 3);
    assert_eq!(file.metadata().unwrap().len(), (OFFSET + 3) as u64);
    assert_eq!(lseek(fd, 0, SeekOrigin::Current).unwrap(), 2);

    let mut first = [0x7f; 2];
    let mut second = [0x7f; 3];
    let mut vectors = [IoSliceMut::new(&mut first), IoSliceMut::new(&mut second)];
    assert!(preadv(fd, &mut vectors, -1).unwrap_err().is_errno(EINVAL));
    assert_eq!(
        preadv(fd, &mut vectors, OFFSET).unwrap(),
        ReadOutcome::Progress(3)
    );
    assert_eq!(
        preadv(fd, &mut vectors, OFFSET + 3).unwrap(),
        ReadOutcome::Eof
    );
    assert_eq!(
        preadv(fd, &mut [], OFFSET + 3).unwrap(),
        ReadOutcome::Progress(0)
    );
    assert_eq!(&first, b"AB");
    assert_eq!(&second, b"c\x7f\x7f");
    assert_eq!(lseek(fd, 0, SeekOrigin::Current).unwrap(), 2);
    let mut prefix = [0; 3];
    assert_eq!(
        pread64(fd, &mut prefix, 0).unwrap(),
        ReadOutcome::Progress(3)
    );
    assert_eq!(&prefix, b"old");
}

#[test]
fn native_v2_distinguishes_explicit_offsets_cursor_and_append() {
    let scratch = Scratch::new();
    let path = scratch.0.join("file");
    fs::write(&path, b"abcdef").unwrap();
    let file = OpenOptions::new()
        .read(true)
        .write(true)
        .open(&path)
        .unwrap();
    let fd = file.as_fd();
    lseek(fd, 1, SeekOrigin::Start).unwrap();
    let mut first = [0; 1];
    let mut second = [0; 1];
    let mut output = [IoSliceMut::new(&mut first), IoSliceMut::new(&mut second)];
    assert!(matches!(
        preadv2(fd, &mut output, Some(-1)),
        Err(SyscallError::InvalidInput(_))
    ));
    assert_eq!(
        preadv2(fd, &mut output, None).unwrap(),
        ReadOutcome::Progress(2)
    );
    assert_eq!((first, second), (*b"b", *b"c"));
    assert_eq!(lseek(fd, 0, SeekOrigin::Current).unwrap(), 3);
    let mut observed = [0; 1];
    let mut output = [IoSliceMut::new(&mut observed)];
    assert_eq!(
        preadv2(fd, &mut output, Some(4)).unwrap(),
        ReadOutcome::Progress(1)
    );
    assert_eq!(&observed, b"e");
    assert_eq!(lseek(fd, 0, SeekOrigin::Current).unwrap(), 3);

    let data = [IoSlice::new(b"X"), IoSlice::new(b"Y")];
    assert!(matches!(
        pwritev2(fd, &data, Some(-1), WriteVectorMode::Default),
        Err(SyscallError::InvalidInput(_))
    ));
    assert_eq!(
        pwritev2(fd, &data, None, WriteVectorMode::Default).unwrap(),
        2
    );
    assert_eq!(lseek(fd, 0, SeekOrigin::Current).unwrap(), 5);
    assert_eq!(fs::read(&path).unwrap(), b"abcXYf");
    let suffix = [IoSlice::new(b"Z"), IoSlice::new(b"!")];
    assert_eq!(
        pwritev2(fd, &suffix, Some(0), WriteVectorMode::Append).unwrap(),
        2
    );
    assert_eq!(lseek(fd, 0, SeekOrigin::Current).unwrap(), 5);
    assert_eq!(fs::read(&path).unwrap(), b"abcXYfZ!");
    assert_eq!(
        pwritev2(fd, &[IoSlice::new(b".")], None, WriteVectorMode::Append).unwrap(),
        1
    );
    assert_eq!(lseek(fd, 0, SeekOrigin::Current).unwrap(), 9);
    let readonly = File::open(&path).unwrap();
    assert!(
        pwritev2(readonly.as_fd(), &suffix, Some(0), WriteVectorMode::Append)
            .unwrap_err()
            .is_errno(EBADF)
    );

    let native_append = OpenOptions::new().append(true).open(&path).unwrap();
    assert_eq!(
        pwritev(native_append.as_fd(), &[IoSlice::new(b"?")], 0).unwrap(),
        1
    );
    assert_eq!(
        lseek(native_append.as_fd(), 0, SeekOrigin::Current).unwrap(),
        0
    );
    assert_eq!(fs::read(&path).unwrap(), b"abcXYfZ!.?");
}

#[test]
fn native_v2_nonblocking_pipe_keeps_partial_write_bytes() {
    let (reader, writer) = pipe2(O_NONBLOCK).unwrap();
    let source: Vec<u8> = (0..1_048_576).map(|index| (index % 251) as u8).collect();
    let requests = [IoSlice::new(&source[..3]), IoSlice::new(&source[3..])];
    let count = pwritev2(writer.borrow(), &requests, None, WriteVectorMode::Default).unwrap();
    assert!((3..source.len()).contains(&count));
    assert!(pwritev2(
        writer.borrow(),
        &requests[..1],
        None,
        WriteVectorMode::Default
    )
    .unwrap_err()
    .is_errno(EAGAIN));
    let mut target = vec![0x7f; count + 2];
    let (first, second) = target.split_at_mut(3);
    let mut result = [IoSliceMut::new(first), IoSliceMut::new(second)];
    assert_eq!(
        preadv2(reader.borrow(), &mut result, None).unwrap(),
        ReadOutcome::Progress(count)
    );
    close(writer).unwrap();
    assert_eq!(
        preadv2(reader.borrow(), &mut result, None).unwrap(),
        ReadOutcome::Eof
    );
    assert_eq!(&target[..count], &source[..count]);
    assert_eq!(&target[count..], &[0x7f, 0x7f]);
}
