use linux_syscalls_provider::*;
use std::net::{Ipv4Addr, SocketAddrV4};
use std::os::fd::AsFd;

const FD_CLOEXEC: i32 = 1;
const EMSGSIZE: i32 = 90;

fn bound() -> (UdpSocket4, SocketAddrV4) {
    let socket = socket_udp4().unwrap();
    assert_eq!(
        fcntl_getfd(socket.as_fd()).unwrap() & FD_CLOEXEC,
        FD_CLOEXEC
    );
    bind_udp4(&socket, SocketAddrV4::new(Ipv4Addr::LOCALHOST, 0)).unwrap();
    let address = getsockname_udp4(&socket).unwrap();
    assert_eq!(*address.ip(), Ipv4Addr::LOCALHOST);
    assert_ne!(address.port(), 0);
    (socket, address)
}

fn ready(socket: &UdpSocket4, milliseconds: i32) -> bool {
    let mut entries = [PollEntry::new(socket.as_fd(), POLLIN)];
    let count = poll(&mut entries, milliseconds).unwrap();
    if count == 0 {
        assert_eq!(entries[0].returned(), 0);
        false
    } else {
        assert_eq!(count, 1);
        assert_ne!(entries[0].returned() & POLLIN, 0);
        true
    }
}

#[test]
fn udp4_preserves_packet_boundaries_source_empty_and_truncation() {
    let (receiver, address) = bound();
    let (sender, peer) = bound();
    assert_eq!(sendto_udp4(&sender, b"abcdef", address).unwrap(), 6);
    assert_eq!(sendto_udp4(&sender, b"", address).unwrap(), 0);
    assert_eq!(sendto_udp4(&sender, b"xyz", address).unwrap(), 3);
    assert_eq!(sendto_udp4(&sender, b"one", address).unwrap(), 3);
    assert_eq!(sendto_udp4(&sender, b"", address).unwrap(), 0);

    assert!(ready(&receiver, 2_000));
    let mut short = [0_u8; 2];
    let truncated = recvfrom_udp4(&receiver, &mut short).unwrap();
    assert_eq!(
        truncated,
        Datagram4 {
            peer,
            bytes_written: 2,
            datagram_len: 6
        }
    );
    assert!(truncated.truncated());
    assert_eq!(&short, b"ab");

    let mut capacity = [0xff; 5];
    assert!(ready(&receiver, 2_000));
    let empty = recvfrom_udp4(&receiver, &mut capacity).unwrap();
    assert_eq!(
        empty,
        Datagram4 {
            peer,
            bytes_written: 0,
            datagram_len: 0
        }
    );
    assert!(!empty.truncated());
    assert_eq!(capacity, [0xff; 5]);

    assert!(ready(&receiver, 2_000));
    let ordinary = recvfrom_udp4(&receiver, &mut capacity).unwrap();
    assert_eq!(
        ordinary,
        Datagram4 {
            peer,
            bytes_written: 3,
            datagram_len: 3
        }
    );
    assert_eq!(capacity, [b'x', b'y', b'z', 0xff, 0xff]);

    assert!(ready(&receiver, 2_000));
    let discarded = recvfrom_udp4(&receiver, &mut []).unwrap();
    assert_eq!(
        discarded,
        Datagram4 {
            peer,
            bytes_written: 0,
            datagram_len: 3
        }
    );
    assert!(discarded.truncated());

    assert!(ready(&receiver, 2_000));
    assert_eq!(recvfrom_udp4(&receiver, &mut []).unwrap(), empty);
    assert!(!ready(&receiver, 0));
    close(sender.into_fd()).unwrap();
    close(receiver.into_fd()).unwrap();
}

#[test]
fn udp4_connect_filters_other_source() {
    let (receiver, address) = bound();
    let (expected, expected_address) = bound();
    let (other, _) = bound();
    connect_udp4(&receiver, expected_address).unwrap();
    assert_eq!(getsockname_udp4(&receiver).unwrap(), address);

    assert_eq!(sendto_udp4(&other, b"x", address).unwrap(), 1);
    assert!(!ready(&receiver, 25));
    assert_eq!(sendto_udp4(&expected, b"y", address).unwrap(), 1);
    assert!(ready(&receiver, 2_000));

    let mut received = [0_u8; 1];
    let packet = recvfrom_udp4(&receiver, &mut received).unwrap();
    assert_eq!(packet.peer, expected_address);
    assert_eq!(&received, b"y");
    assert!(!ready(&receiver, 0));
}

#[test]
fn udp4_rejects_oversized_datagram_and_keeps_socket() {
    let (receiver, address) = bound();
    let (sender, peer) = bound();
    let oversized = vec![0xff; 65_536];
    assert!(sendto_udp4(&sender, &oversized, address)
        .unwrap_err()
        .is_errno(EMSGSIZE));
    assert!(!ready(&receiver, 0));

    let payload = [7];
    assert_eq!(sendto_udp4(&sender, &payload, address).unwrap(), 1);
    assert!(ready(&receiver, 2_000));
    let mut received = [0_u8; 1];
    assert_eq!(recvfrom_udp4(&receiver, &mut received).unwrap().peer, peer);
    assert_eq!(received, payload);
}
