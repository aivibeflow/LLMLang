use linux_syscalls_provider::*;
use std::io::{IoSlice, IoSliceMut};
use std::mem::size_of;
use std::net::{Ipv4Addr, SocketAddrV4};
use std::os::fd::{AsFd, AsRawFd};
use std::os::raw::{c_int, c_uint, c_void};

const EMSGSIZE: i32 = 90;
const SOL_IP: c_int = 0;
const IP_PKTINFO: c_int = 8;

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

fn bound() -> (UdpSocket4, SocketAddrV4) {
    let socket = socket_udp4().unwrap();
    bind_udp4(&socket, SocketAddrV4::new(Ipv4Addr::LOCALHOST, 0)).unwrap();
    let address = getsockname_udp4(&socket).unwrap();
    assert_eq!(*address.ip(), Ipv4Addr::LOCALHOST);
    assert_ne!(address.port(), 0);
    (socket, address)
}

fn ready(socket: &UdpSocket4, milliseconds: i32) -> bool {
    let mut events = [PollEntry::new(socket.as_fd(), POLLIN)];
    match poll(&mut events, milliseconds).unwrap() {
        0 => false,
        1 => {
            assert_ne!(events[0].returned() & POLLIN, 0);
            true
        }
        count => panic!("invalid readiness count {count}"),
    }
}

#[test]
fn udp_messages_preserve_scatter_order_peer_and_truncation() {
    let (receiver, address) = bound();
    let (sender, peer) = bound();
    let large = [
        IoSlice::new(b"ab"),
        IoSlice::new(b""),
        IoSlice::new(b"cdef"),
    ];
    assert_eq!(sendmsg_udp4(&sender, &large, address).unwrap(), 6);
    assert_eq!(sendmsg_udp4(&sender, &[], address).unwrap(), 0);
    let short = [IoSlice::new(b"x"), IoSlice::new(b"yz")];
    assert_eq!(sendmsg_udp4(&sender, &short, address).unwrap(), 3);
    assert_eq!(sendmsg_udp4(&sender, &short, address).unwrap(), 3);

    let mut head = [0xFF; 1];
    let mut tail = [0xFF; 3];
    assert!(ready(&receiver, 2_000));
    let large = recvmsg_udp4(
        &receiver,
        &mut [IoSliceMut::new(&mut head), IoSliceMut::new(&mut tail)],
    )
    .unwrap();
    assert_eq!(
        large.datagram,
        Datagram4 {
            peer,
            bytes_written: 4,
            datagram_len: 6
        }
    );
    assert!(large.data_truncated);
    assert!(!large.control_truncated);
    assert_eq!(large.unsupported_flags, 0);
    assert_eq!(&head, b"a");
    assert_eq!(&tail, b"bcd");

    assert!(ready(&receiver, 2_000));
    let empty = recvmsg_udp4(&receiver, &mut []).unwrap();
    assert_eq!(
        empty.datagram,
        Datagram4 {
            peer,
            bytes_written: 0,
            datagram_len: 0
        }
    );
    assert!(!empty.data_truncated);

    assert!(ready(&receiver, 2_000));
    let discarded = recvmsg_udp4(&receiver, &mut []).unwrap();
    assert_eq!(
        discarded.datagram,
        Datagram4 {
            peer,
            bytes_written: 0,
            datagram_len: 3
        }
    );
    assert!(discarded.data_truncated);

    assert!(ready(&receiver, 2_000));
    let small = recvmsg_udp4(
        &receiver,
        &mut [IoSliceMut::new(&mut head), IoSliceMut::new(&mut tail)],
    )
    .unwrap();
    assert_eq!(
        small.datagram,
        Datagram4 {
            peer,
            bytes_written: 3,
            datagram_len: 3
        }
    );
    assert!(!small.data_truncated);
    assert_eq!(&head, b"x");
    assert_eq!(tail, [b'y', b'z', b'd']);
    assert!(!ready(&receiver, 0));

    close(sender.into_fd()).unwrap();
    close(receiver.into_fd()).unwrap();
}

#[test]
fn udp_messages_preserve_oversize_errno_and_vector_limits() {
    let (receiver, address) = bound();
    let (sender, _) = bound();
    let oversized = vec![0xAE; 65_536];
    let buffers = [
        IoSlice::new(&oversized[..4_096]),
        IoSlice::new(&oversized[4_096..]),
    ];
    assert!(sendmsg_udp4(&sender, &buffers, address)
        .unwrap_err()
        .is_errno(EMSGSIZE));
    assert!(!ready(&receiver, 0));

    let vectors = [IoSlice::new(b""); 1025];
    assert!(matches!(
        sendmsg_udp4(&sender, &vectors, address),
        Err(SyscallError::InvalidInput(_))
    ));
    let mut bytes = vec![[0_u8; 1]; 1025];
    let mut vectors: Vec<_> = bytes.iter_mut().map(|byte| IoSliceMut::new(byte)).collect();
    assert!(matches!(
        recvmsg_udp4(&receiver, &mut vectors),
        Err(SyscallError::InvalidInput(_))
    ));

    assert_eq!(
        sendmsg_udp4(&sender, &[IoSlice::new(b"x")], address).unwrap(),
        1
    );
    assert!(ready(&receiver, 2_000));
    let mut buffer = [0];
    assert_eq!(
        recvmsg_udp4(&receiver, &mut [IoSliceMut::new(&mut buffer)])
            .unwrap()
            .datagram
            .datagram_len,
        1
    );
    assert_eq!(&buffer, b"x");
}

#[test]
fn udp_messages_report_discarded_packet_metadata() {
    let (receiver, address) = bound();
    let (sender, peer) = bound();
    let enabled: c_int = 1;
    // Ask only the loopback fixture to request IP_PKTINFO. The provider
    // never passes a control buffer or returns any packet metadata.
    assert_eq!(
        unsafe {
            libc_setsockopt(
                receiver.as_fd().as_raw_fd(),
                SOL_IP,
                IP_PKTINFO,
                (&enabled as *const c_int).cast(),
                size_of::<c_int>() as c_uint,
            )
        },
        0
    );
    let input = [IoSlice::new(b"local")];
    assert_eq!(sendmsg_udp4(&sender, &input, address).unwrap(), 5);
    assert!(ready(&receiver, 2_000));
    let mut buffer = [0; 2];
    let result = recvmsg_udp4(&receiver, &mut [IoSliceMut::new(&mut buffer)]).unwrap();
    assert_eq!(
        result.datagram,
        Datagram4 {
            peer,
            bytes_written: 2,
            datagram_len: 5
        }
    );
    assert!(result.data_truncated);
    assert!(result.control_truncated);
    assert_eq!(result.unsupported_flags, 0);
    assert_eq!(&buffer, b"lo");
}
