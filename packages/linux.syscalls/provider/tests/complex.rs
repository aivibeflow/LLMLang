use linux_syscalls_provider::{
    close, fcntl_getfd, io_uring_register_probe, io_uring_setup, perf_event_open_task_clock, read,
    ReadOutcome, SyscallError, ENOSYS,
};
use std::hint::black_box;
use std::os::fd::{AsFd, BorrowedFd};

const EPERM: i32 = 1;
const ENOENT: i32 = 2;
const EACCES: i32 = 13;
const EOPNOTSUPP: i32 = 95;

fn assert_unavailable(error: SyscallError, accepted: &[i32]) {
    assert!(accepted.iter().any(|&code| error.is_errno(code)), "{error}");
    println!("availability outcome: {error}");
}

fn read_counter(fd: BorrowedFd<'_>) -> u64 {
    let mut result = [0_u8; 8];
    assert_eq!(read(fd, &mut result).unwrap(), ReadOutcome::Progress(8));
    u64::from_ne_bytes(result)
}

#[test]
fn native_perf_task_clock_or_exact_unavailable_errno() {
    match perf_event_open_task_clock() {
        Ok(fd) => {
            assert_eq!(fcntl_getfd(fd.borrow()).unwrap() & 1, 1);
            let before = read_counter(fd.borrow());
            for value in 1..=10000 {
                black_box(value);
            }
            assert!(read_counter(fd.borrow()) >= before);
            close(fd).unwrap();
        }
        Err(error) => assert_unavailable(error, &[EPERM, EACCES, ENOSYS, ENOENT, EOPNOTSUPP]),
    }
}

#[test]
fn native_io_uring_probe_or_exact_unavailable_errno() {
    let (ring, info) = match io_uring_setup(3) {
        Ok(result) => result,
        Err(error) => {
            assert_unavailable(error, &[EPERM, EACCES, ENOSYS]);
            return;
        }
    };
    assert_eq!(fcntl_getfd(ring.borrow()).unwrap() & 1, 1);
    assert_eq!(info.submission_entries, 4);
    assert_eq!(info.completion_entries, 8);
    match io_uring_register_probe(ring.borrow()) {
        Ok(probe) => {
            assert_eq!(probe.operations.len(), usize::from(probe.last_opcode) + 1);
            for (opcode, operation) in probe.operations.iter().enumerate() {
                assert_eq!(usize::from(operation.opcode), opcode);
            }
            assert_eq!(probe.operations[0].flags & 1, 1);
        }
        Err(error) => assert_unavailable(error, &[EPERM, EACCES, ENOSYS]),
    }
    close(ring).unwrap();
}

#[test]
fn native_io_uring_rejects_out_of_profile_depth() {
    for entries in [0, 257, u32::MAX] {
        assert!(matches!(
            io_uring_setup(entries),
            Err(SyscallError::InvalidInput(_))
        ));
    }
}

#[test]
fn native_io_uring_probe_rejects_non_ring_descriptor() {
    let file = std::fs::File::open("/dev/null").unwrap();
    assert_unavailable(
        io_uring_register_probe(file.as_fd()).unwrap_err(),
        &[EOPNOTSUPP, EPERM, EACCES, ENOSYS],
    );
}
