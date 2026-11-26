use linux_syscalls_provider::*;
use std::fs::{self, File, OpenOptions};
use std::io::IoSliceMut;
use std::os::fd::AsFd;
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

const ESPIPE: i32 = 29;

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
            "llmlang-pipe-transfer-{}-{timestamp}-{number}",
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
fn native_splice_keeps_file_cursors_and_partial_offsets() {
    let scratch = Scratch::new();
    let source = scratch.0.join("source");
    let destination = scratch.0.join("destination");
    fs::write(&source, b"abcdefgh").unwrap();
    fs::write(&destination, b"........").unwrap();
    let input_file = File::open(&source).unwrap();
    let output_file = OpenOptions::new()
        .read(true)
        .write(true)
        .open(&destination)
        .unwrap();
    let input = input_file.as_fd();
    let output = output_file.as_fd();
    lseek(input, 2, SeekOrigin::Start).unwrap();
    lseek(output, 1, SeekOrigin::Start).unwrap();
    let (reader, writer) = pipe2(O_NONBLOCK).unwrap();
    let mode = SpliceMode::NonBlocking;
    let mut read_at = 5;
    let mut write_at = 4;
    let mut invalid_pipe_offset = 0;
    assert!(splice(
        input,
        None,
        writer.borrow(),
        Some(&mut invalid_pipe_offset),
        1,
        mode
    )
    .unwrap_err()
    .is_errno(ESPIPE));
    assert_eq!(invalid_pipe_offset, 0);
    assert_eq!(lseek(input, 0, SeekOrigin::Current).unwrap(), 2);

    assert_eq!(
        splice(input, Some(&mut read_at), writer.borrow(), None, 64, mode).unwrap(),
        3
    );
    assert_eq!(read_at, 8);
    assert_eq!(lseek(input, 0, SeekOrigin::Current).unwrap(), 2);
    assert_eq!(
        splice(reader.borrow(), None, output, Some(&mut write_at), 64, mode).unwrap(),
        3
    );
    assert_eq!(write_at, 7);
    assert_eq!(lseek(output, 0, SeekOrigin::Current).unwrap(), 1);
    assert_eq!(fs::read(&destination).unwrap(), b"....fgh.");
    assert!(
        splice(reader.borrow(), None, output, Some(&mut write_at), 1, mode)
            .unwrap_err()
            .is_errno(EAGAIN)
    );
    assert_eq!(write_at, 7);
    assert_eq!(
        splice(input, Some(&mut read_at), writer.borrow(), None, 64, mode).unwrap(),
        0
    );
    assert_eq!(read_at, 8);

    assert_eq!(
        splice(input, None, writer.borrow(), None, 2, mode).unwrap(),
        2
    );
    assert_eq!(lseek(input, 0, SeekOrigin::Current).unwrap(), 4);
    assert_eq!(
        splice(reader.borrow(), None, output, None, 2, mode).unwrap(),
        2
    );
    assert_eq!(lseek(output, 0, SeekOrigin::Current).unwrap(), 3);
    assert_eq!(fs::read(&destination).unwrap(), b".cd.fgh.");
    assert_eq!(fs::read(&source).unwrap(), b"abcdefgh");
}

#[test]
fn native_tee_duplicates_prefix_without_consuming_input() {
    let (input, writer) = pipe2(0).unwrap();
    let (result, output) = pipe2(0).unwrap();
    let mode = SpliceMode::NonBlocking;
    assert!(tee(input.borrow(), output.borrow(), 1, mode)
        .unwrap_err()
        .is_errno(EAGAIN));
    assert_eq!(write(writer.borrow(), b"abc\0d").unwrap(), 5);
    assert!(tee(input.borrow(), writer.borrow(), 1, mode)
        .unwrap_err()
        .is_errno(EINVAL));
    assert_eq!(tee(input.borrow(), output.borrow(), 64, mode).unwrap(), 5);
    let mut source = [0xff; 6];
    let mut destination = [0xff; 6];
    assert_eq!(
        read(input.borrow(), &mut source).unwrap(),
        ReadOutcome::Progress(5)
    );
    assert_eq!(
        read(result.borrow(), &mut destination).unwrap(),
        ReadOutcome::Progress(5)
    );
    assert_eq!(&source, b"abc\0d\xff");
    assert_eq!(source, destination);
    close(writer).unwrap();
    assert_eq!(tee(input.borrow(), output.borrow(), 64, mode).unwrap(), 0);
}

#[test]
fn native_vmsplice_copies_only_into_owned_read_end() {
    let mode = SpliceMode::NonBlocking;
    let (reader, writer) = vmsplice_pipe(SpliceMode::Blocking).unwrap();
    assert_eq!(fcntl_getfl(reader.borrow()).unwrap() & 3, O_RDONLY);
    assert_eq!(fcntl_getfl(writer.borrow()).unwrap() & 3, O_WRONLY);
    assert_eq!(fcntl_getfl(reader.borrow()).unwrap() & O_NONBLOCK, 0);
    assert_eq!(fcntl_getfd(reader.borrow()).unwrap() & 1, 1);
    assert_eq!(fcntl_getfd(writer.borrow()).unwrap() & 1, 1);
    let mut first = [0xff; 1];
    let mut second = [0xff; 4];
    let mut output = [IoSliceMut::new(&mut first), IoSliceMut::new(&mut second)];
    assert!(vmsplice(&reader, &mut output, mode)
        .unwrap_err()
        .is_errno(EAGAIN));
    assert_eq!(
        vmsplice(&reader, &mut [], mode).unwrap(),
        ReadOutcome::Progress(0)
    );
    assert_eq!(write(writer.borrow(), b"a\0b").unwrap(), 3);
    assert_eq!(
        vmsplice(&reader, &mut output, mode).unwrap(),
        ReadOutcome::Progress(3)
    );
    assert_eq!(&first, b"a");
    assert_eq!(&second, b"\0b\xff\xff");
    first.fill(0x7f);
    second.fill(0x7f);
    assert_eq!(write(writer.borrow(), b"next").unwrap(), 4);
    let mut expected = [0; 4];
    assert_eq!(
        read(reader.borrow(), &mut expected).unwrap(),
        ReadOutcome::Progress(4)
    );
    assert_eq!(&expected, b"next");
    assert_eq!(first, [0x7f]);
    assert_eq!(second, [0x7f; 4]);
    close(writer).unwrap();
    assert_eq!(
        vmsplice(&reader, &mut [IoSliceMut::new(&mut expected)], mode).unwrap(),
        ReadOutcome::Eof
    );
    close(reader.into_fd()).unwrap();

    let (nonblocking, writer) = vmsplice_pipe(mode).unwrap();
    assert_eq!(
        fcntl_getfl(nonblocking.borrow()).unwrap() & O_NONBLOCK,
        O_NONBLOCK
    );
    assert_eq!(
        fcntl_getfl(writer.borrow()).unwrap() & O_NONBLOCK,
        O_NONBLOCK
    );
    close(nonblocking.into_fd()).unwrap();
    close(writer).unwrap();
}
