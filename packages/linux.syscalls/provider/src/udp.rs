use super::{
    abi, bind, connect, decode_nonnegative, getsockname, LinuxFd, SyscallError, O_CLOEXEC,
};
use crate::socket::SockaddrIn;
use std::mem::size_of;
use std::net::SocketAddrV4;
use std::os::fd::{AsFd, AsRawFd, BorrowedFd};

const AF_INET: usize = 2;
const SOCK_DGRAM: usize = 2;
const IPPROTO_UDP: usize = 17;
const MSG_TRUNC: usize = 0x20;
const MSG_NOSIGNAL: usize = 0x4000;

/// Owned descriptor for a native IPv4 UDP socket.
#[derive(Debug)]
pub struct UdpSocket4(LinuxFd);

impl UdpSocket4 {
    /// Transfer descriptor ownership to a generic operation such as close.
    pub fn into_fd(self) -> LinuxFd {
        self.0
    }
}

impl AsFd for UdpSocket4 {
    fn as_fd(&self) -> BorrowedFd<'_> {
        self.0.borrow()
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Datagram4 {
    pub peer: SocketAddrV4,
    /// Number of initialized bytes in the caller's buffer.
    pub bytes_written: usize,
    /// Length of the original UDP payload, including any discarded tail.
    pub datagram_len: usize,
}

impl Datagram4 {
    pub fn truncated(self) -> bool {
        self.bytes_written < self.datagram_len
    }
}

/// Create an IPv4 UDP socket with FD_CLOEXEC set atomically.
pub fn socket_udp4() -> Result<UdpSocket4, SyscallError> {
    let raw = unsafe {
        abi::invoke(
            abi::SOCKET,
            [
                AF_INET,
                SOCK_DGRAM | O_CLOEXEC as usize,
                IPPROTO_UDP,
                0,
                0,
                0,
            ],
        )
    };
    Ok(UdpSocket4(LinuxFd::from_result(raw)?))
}

pub fn bind_udp4(socket: &UdpSocket4, address: SocketAddrV4) -> Result<(), SyscallError> {
    bind(socket.as_fd(), address)
}

pub fn connect_udp4(socket: &UdpSocket4, peer: SocketAddrV4) -> Result<(), SyscallError> {
    connect(socket.as_fd(), peer)
}

pub fn getsockname_udp4(socket: &UdpSocket4) -> Result<SocketAddrV4, SyscallError> {
    getsockname(socket.as_fd())
}

/// Submit one UDP datagram to the supplied peer. A successful send accepts
/// the whole payload into the network stack without guaranteeing delivery.
pub fn sendto_udp4(
    socket: &UdpSocket4,
    payload: &[u8],
    peer: SocketAddrV4,
) -> Result<usize, SyscallError> {
    let address = SockaddrIn::from(peer);
    let raw = unsafe {
        abi::invoke(
            abi::SENDTO,
            [
                socket.as_fd().as_raw_fd() as usize,
                payload.as_ptr() as usize,
                payload.len(),
                MSG_NOSIGNAL,
                (&address as *const SockaddrIn) as usize,
                size_of::<SockaddrIn>(),
            ],
        )
    };
    let accepted = decode_nonnegative(raw)?;
    if accepted != payload.len() {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    Ok(accepted)
}

/// Consume one IPv4 datagram. An empty datagram is successful, including with
/// an empty destination buffer. MSG_TRUNC makes the full packet length
/// available even when only a prefix fits in the destination.
pub fn recvfrom_udp4(socket: &UdpSocket4, buffer: &mut [u8]) -> Result<Datagram4, SyscallError> {
    let mut address = SockaddrIn::default();
    let mut address_len = size_of::<SockaddrIn>() as u32;
    let raw = unsafe {
        abi::invoke(
            abi::RECVFROM,
            [
                socket.as_fd().as_raw_fd() as usize,
                buffer.as_mut_ptr() as usize,
                buffer.len(),
                MSG_TRUNC,
                (&mut address as *mut SockaddrIn) as usize,
                (&mut address_len as *mut u32) as usize,
            ],
        )
    };
    let datagram_len = decode_nonnegative(raw)?;
    let peer = address
        .public_address(address_len)
        .map_err(|_| SyscallError::UnexpectedReturn(raw))?;
    Ok(Datagram4 {
        peer,
        bytes_written: datagram_len.min(buffer.len()),
        datagram_len,
    })
}
