use linux_syscalls_provider::*;
use std::io::{IoSlice, IoSliceMut};
use std::mem::size_of;
use std::net::{Ipv4Addr, SocketAddrV4};
use std::os::fd::{AsFd, AsRawFd};
use std::os::raw::{c_int, c_uint, c_void};
use std::os::unix::net::UnixStream;

const ENOTSOCK: i32 = 88;
const SOL_SOCKET: c_int = 1;
const SO_PASSCRED: c_int = 16;

extern "C" {
    #[link_name = "setsockopt"]
    fn libc_setsockopt(
        fd: c_int,
        level: c_int,
        option: c_int,
        value: *const c_void,
        len: c_uint,
    ) -> c_int;
}

fn compare_stream_order(sender: &LinuxFd, receiver: &LinuxFd) {
    assert_eq!(sendmsg(sender.borrow(), &[]).unwrap(), 0);
    assert_eq!(
        sendmsg(
            sender.borrow(),
            &[IoSlice::new(&[1, 0, 2]), IoSlice::new(&[3, 4])]
        )
        .unwrap(),
        5
    );
    shutdown(sender.borrow(), Shutdown::Write).unwrap();

    let mut first = [0xff; 2];
    let mut tail = [0xff; 6];
    let received = recvmsg(
        receiver.borrow(),
        &mut [IoSliceMut::new(&mut first), IoSliceMut::new(&mut tail)],
    )
    .unwrap();
    assert_eq!(
        received,
        ReceivedStreamMessage {
            outcome: ReadOutcome::Progress(5),
            data_truncated: false,
            control_truncated: false,
            unsupported_flags: 0,
        }
    );
    assert_eq!(first, [1, 0]);
    assert_eq!(tail, [2, 3, 4, 0xff, 0xff, 0xff]);
    assert_eq!(
        recvmsg(receiver.borrow(), &mut []).unwrap().outcome,
        ReadOutcome::Progress(0)
    );
    assert_eq!(
        recvmsg(receiver.borrow(), &mut [IoSliceMut::new(&mut tail)])
            .unwrap()
            .outcome,
        ReadOutcome::Eof
    );
}

#[test]
fn stream_messages_preserve_vector_order_and_eof() {
    let (left, right) = socketpair().unwrap();
    compare_stream_order(&left, &right);
    close(left).unwrap();
    close(right).unwrap();

    let listener = socket().unwrap();
    bind(listener.borrow(), SocketAddrV4::new(Ipv4Addr::LOCALHOST, 0)).unwrap();
    listen(listener.borrow(), 1).unwrap();
    let client = socket().unwrap();
    connect(client.borrow(), getsockname(listener.borrow()).unwrap()).unwrap();
    let server = accept4(listener.borrow()).unwrap();
    compare_stream_order(&client, &server);
    close(client).unwrap();
    close(server).unwrap();
    close(listener).unwrap();
}

#[test]
fn stream_message_reports_partial_progress_and_errno() {
    let (first, second) = UnixStream::pair().unwrap();
    first.set_nonblocking(true).unwrap();
    second.set_nonblocking(true).unwrap();
    let mut buffer = [0; 32];
    assert!(recvmsg(second.as_fd(), &mut [IoSliceMut::new(&mut buffer)])
        .unwrap_err()
        .is_errno(EAGAIN));

    let input: Vec<u8> = (0..1_048_576).map(|offset| (offset % 251) as u8).collect();
    let sent = sendmsg(
        first.as_fd(),
        &[IoSlice::new(&input[..4]), IoSlice::new(&input[4..])],
    )
    .unwrap();
    assert!((5..input.len()).contains(&sent));
    let mut head = [0xFF; 4];
    let mut rest = vec![0xFF; sent];
    let received = recvmsg(
        second.as_fd(),
        &mut [IoSliceMut::new(&mut head), IoSliceMut::new(&mut rest)],
    )
    .unwrap();
    assert_eq!(received.outcome, ReadOutcome::Progress(sent));
    assert_eq!(&head[..], &input[..4]);
    assert_eq!(&rest[..sent - 4], &input[4..sent]);
    assert_eq!(&rest[sent - 4..], &[0xff; 4]);

    drop(second);
    assert!(sendmsg(first.as_fd(), &[IoSlice::new(b"x")])
        .unwrap_err()
        .is_errno(EPIPE));
    let (reader, _writer) = pipe2(0).unwrap();
    assert!(sendmsg(reader.borrow(), &[IoSlice::new(b"x")])
        .unwrap_err()
        .is_errno(ENOTSOCK));
    assert!(
        recvmsg(reader.borrow(), &mut [IoSliceMut::new(&mut buffer)])
            .unwrap_err()
            .is_errno(ENOTSOCK)
    );
}

#[test]
fn stream_message_reports_discarded_ancillary_data() {
    let (sender, receiver) = socketpair().unwrap();
    let enabled: c_int = 1;
    // The test uses the receiving end's local Unix credentials option to
    // have the kernel generate ancillary data. The provider exposes no
    // control messages or generic socket-option entry point.
    assert_eq!(
        unsafe {
            libc_setsockopt(
                receiver.borrow().as_raw_fd(),
                SOL_SOCKET,
                SO_PASSCRED,
                (&enabled as *const c_int).cast(),
                size_of::<c_int>() as c_uint,
            )
        },
        0
    );
    assert_eq!(sendmsg(sender.borrow(), &[IoSlice::new(b"z")]).unwrap(), 1);
    let mut output = [0];
    let result = recvmsg(receiver.borrow(), &mut [IoSliceMut::new(&mut output)]).unwrap();
    assert_eq!(result.outcome, ReadOutcome::Progress(1));
    assert!(result.control_truncated);
    assert!(!result.data_truncated);
    assert_eq!(result.unsupported_flags, 0);
    assert_eq!(&output, b"z");
}

#[test]
fn stream_messages_validate_iovec_limits() {
    let (sender, receiver) = socketpair().unwrap();
    let vectors = [IoSlice::new(b""); 1025];
    assert!(matches!(
        sendmsg(sender.borrow(), &vectors),
        Err(SyscallError::InvalidInput(_))
    ));
    let mut bytes = vec![[0_u8; 1]; 1025];
    let mut vectors: Vec<_> = bytes.iter_mut().map(|byte| IoSliceMut::new(byte)).collect();
    assert!(matches!(
        recvmsg(receiver.borrow(), &mut vectors),
        Err(SyscallError::InvalidInput(_))
    ));
    assert_eq!(sendmsg(sender.borrow(), &[IoSlice::new(b"ok")]).unwrap(), 2);
    let mut buffer = [0; 2];
    assert_eq!(
        recvmsg(receiver.borrow(), &mut [IoSliceMut::new(&mut buffer)])
            .unwrap()
            .outcome,
        ReadOutcome::Progress(2)
    );
    assert_eq!(&buffer, b"ok");
}
