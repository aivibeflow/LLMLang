use linux_syscalls_provider::{
    bind_udp4, close, getsockname_udp4, recvmmsg_udp4, sendmmsg_udp4, socket_udp4, SendDatagram4,
    SyscallError, UdpSocket4, EAGAIN,
};
use std::io::{IoSlice, IoSliceMut};
use std::net::{Ipv4Addr, SocketAddrV4};

fn loopback_socket() -> UdpSocket4 {
    let socket = socket_udp4().unwrap();
    bind_udp4(&socket, SocketAddrV4::new(Ipv4Addr::LOCALHOST, 0)).unwrap();
    socket
}

#[test]
fn udp_batch_preserves_order_truncation_empty_packets_and_receive_prefix() {
    let sender = loopback_socket();
    let receiver = loopback_socket();
    let peer = getsockname_udp4(&receiver).unwrap();
    let source = getsockname_udp4(&sender).unwrap();
    let words = [IoSlice::new(b"one"), IoSlice::new(b"-two")];
    let messages = [
        SendDatagram4 {
            peer,
            buffers: &words,
        },
        SendDatagram4 { peer, buffers: &[] },
    ];
    assert_eq!(sendmmsg_udp4(&sender, &messages).unwrap(), [7, 0]);

    let mut part1 = [0; 2];
    let mut part2 = [0; 1];
    let mut empty = [0xFE; 1];
    let mut unused = [0xAB; 2];
    let mut one = [IoSliceMut::new(&mut part1), IoSliceMut::new(&mut part2)];
    let mut two = [IoSliceMut::new(&mut empty)];
    let mut three = [IoSliceMut::new(&mut unused)];
    let received = recvmmsg_udp4(&receiver, &mut [&mut one, &mut two, &mut three]).unwrap();
    assert_eq!(received.len(), 2);
    assert_eq!(received[0].datagram.peer, source);
    assert_eq!(received[0].datagram.bytes_written, 3);
    assert_eq!(received[0].datagram.datagram_len, 7);
    assert!(received[0].data_truncated);
    assert!(!received[0].control_truncated);
    assert_eq!(received[1].datagram.peer, source);
    assert_eq!(received[1].datagram.bytes_written, 0);
    assert_eq!(received[1].datagram.datagram_len, 0);
    assert!(!received[1].data_truncated);
    assert_eq!(&part1, b"on");
    assert_eq!(&part2, b"e");
    assert_eq!(empty, [0xFE]);
    assert_eq!(unused, [0xAB; 2]);
    assert!(recvmmsg_udp4(&receiver, &mut [&mut []])
        .unwrap_err()
        .is_errno(EAGAIN));
    close(sender.into_fd()).unwrap();
    close(receiver.into_fd()).unwrap();
}

#[test]
fn udp_batch_preserves_send_prefix_and_first_envelope_error() {
    let sender = loopback_socket();
    let receiver = loopback_socket();
    let peer = getsockname_udp4(&receiver).unwrap();
    let normal = [IoSlice::new(b"sent")];
    let oversized_payload = vec![0; 65_508];
    let oversized = [IoSlice::new(&oversized_payload)];
    let good = SendDatagram4 {
        peer,
        buffers: &normal,
    };
    let too_large = SendDatagram4 {
        peer,
        buffers: &oversized,
    };
    assert!(sendmmsg_udp4(&sender, &[too_large, good])
        .unwrap_err()
        .is_errno(90));
    assert_eq!(
        sendmmsg_udp4(&sender, &[good, too_large, good]).unwrap(),
        [4]
    );

    let mut bytes = [0; 4];
    let mut vectors = [IoSliceMut::new(&mut bytes)];
    let received = recvmmsg_udp4(&receiver, &mut [&mut vectors, &mut []]).unwrap();
    assert_eq!(received.len(), 1);
    assert_eq!(received[0].datagram.datagram_len, 4);
    assert_eq!(&bytes, b"sent");
    assert!(recvmmsg_udp4(&receiver, &mut [&mut []])
        .unwrap_err()
        .is_errno(EAGAIN));
    close(sender.into_fd()).unwrap();
    close(receiver.into_fd()).unwrap();
}

#[test]
fn udp_batch_rejects_invalid_shape_before_sending_any_datagram() {
    let sender = loopback_socket();
    let receiver = loopback_socket();
    let peer = getsockname_udp4(&receiver).unwrap();
    let empty = SendDatagram4 { peer, buffers: &[] };
    let excess_vectors = [IoSlice::new(b""); 17];
    let excess = SendDatagram4 {
        peer,
        buffers: &excess_vectors,
    };
    for inputs in [&[][..], &[empty; 33], &[empty, excess]] {
        assert!(matches!(
            sendmmsg_udp4(&sender, inputs),
            Err(SyscallError::InvalidInput(_))
        ));
    }
    assert!(matches!(
        recvmmsg_udp4(&receiver, &mut []),
        Err(SyscallError::InvalidInput(_))
    ));
    assert!(recvmmsg_udp4(&receiver, &mut [&mut []])
        .unwrap_err()
        .is_errno(EAGAIN));
    close(sender.into_fd()).unwrap();
    close(receiver.into_fd()).unwrap();
}
