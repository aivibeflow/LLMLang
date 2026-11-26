use linux_syscalls_provider::*;

const ENOTSOCK: i32 = 88;
const SO_TYPE_STREAM: i32 = 1;
const FD_CLOEXEC: i32 = 1;

fn receive_exact(fd: &LinuxFd, buffer: &mut [u8]) {
    let mut filled = 0;
    while filled < buffer.len() {
        match read(fd.borrow(), &mut buffer[filled..]).unwrap() {
            ReadOutcome::Progress(count) if count > 0 => filled += count,
            outcome => panic!("unexpected local socket read outcome: {outcome:?}"),
        }
    }
}

#[test]
fn unix_socketpair_transfers_bytes_and_closes() {
    let (left, right) = socketpair().unwrap();
    for endpoint in [&left, &right] {
        assert_eq!(
            fcntl_getfd(endpoint.borrow()).unwrap() & FD_CLOEXEC,
            FD_CLOEXEC
        );
    }
    let payload = [0, 0xff, b'a', 0x80];
    assert_eq!(write(left.borrow(), &payload).unwrap(), payload.len());
    let mut buffer = [0_u8; 4];
    receive_exact(&right, &mut buffer);
    assert_eq!(buffer, payload);

    assert_eq!(write(right.borrow(), &payload).unwrap(), payload.len());
    receive_exact(&left, &mut buffer);
    assert_eq!(buffer, payload);

    close(left).unwrap();
    assert_eq!(read(right.borrow(), &mut buffer).unwrap(), ReadOutcome::Eof);
    close(right).unwrap();
}

#[test]
fn socket_type_and_reuseaddr_roundtrip() {
    let socket = socket().unwrap();
    assert_eq!(getsockopt_type(socket.borrow()).unwrap(), SO_TYPE_STREAM);
    assert!(!getsockopt_reuseaddr(socket.borrow()).unwrap());
    setsockopt_reuseaddr(socket.borrow(), true).unwrap();
    assert!(getsockopt_reuseaddr(socket.borrow()).unwrap());
    setsockopt_reuseaddr(socket.borrow(), false).unwrap();
    assert!(!getsockopt_reuseaddr(socket.borrow()).unwrap());
    assert_eq!(getsockopt_type(socket.borrow()).unwrap(), SO_TYPE_STREAM);
    close(socket).unwrap();
}

#[test]
fn socket_options_preserve_non_socket_error() {
    let (read_end, write_end) = pipe2(0).unwrap();
    let borrowed = read_end.borrow();
    assert!(getsockopt_type(borrowed).unwrap_err().is_errno(ENOTSOCK));
    assert!(getsockopt_reuseaddr(borrowed)
        .unwrap_err()
        .is_errno(ENOTSOCK));
    assert!(setsockopt_reuseaddr(borrowed, true)
        .unwrap_err()
        .is_errno(ENOTSOCK));

    assert_eq!(write(write_end.borrow(), &[7]).unwrap(), 1);
    let mut byte = [0];
    receive_exact(&read_end, &mut byte);
    assert_eq!(byte, [7]);
    close(read_end).unwrap();
    close(write_end).unwrap();
}
