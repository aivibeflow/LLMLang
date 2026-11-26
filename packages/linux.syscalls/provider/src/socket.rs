use super::{
    abi, decode_read, decode_write, decode_zero, LinuxFd, ReadOutcome, SyscallError, O_CLOEXEC,
};
use std::mem::size_of;
use std::net::{Ipv4Addr, SocketAddrV4};
use std::os::fd::{AsRawFd, BorrowedFd};

const AF_INET: u16 = 2;
const SOCK_STREAM: usize = 1;
const MSG_NOSIGNAL: usize = 0x4000;

#[repr(C)]
#[derive(Default)]
pub(super) struct SockaddrIn {
    family: u16,
    port_be: u16,
    address_be: u32,
    padding: [u8; 8],
}

impl From<SocketAddrV4> for SockaddrIn {
    fn from(address: SocketAddrV4) -> Self {
        Self {
            family: AF_INET,
            port_be: address.port().to_be(),
            address_be: u32::from_ne_bytes(address.ip().octets()),
            padding: [0; 8],
        }
    }
}

impl SockaddrIn {
    pub(super) fn public_address(self, len: u32) -> Result<SocketAddrV4, SyscallError> {
        if self.family != AF_INET || len as usize != size_of::<Self>() {
            return Err(SyscallError::InvalidInput(
                "socket address does not have the declared IPv4 layout",
            ));
        }
        Ok(SocketAddrV4::new(
            Ipv4Addr::from(self.address_be.to_ne_bytes()),
            u16::from_be(self.port_be),
        ))
    }
}

/// Constructs an IPv4 TCP stream socket with FD_CLOEXEC set atomically.
pub fn socket() -> Result<LinuxFd, SyscallError> {
    let raw = unsafe {
        abi::call(
            abi::SOCKET,
            [
                AF_INET as usize,
                SOCK_STREAM | O_CLOEXEC as usize,
                0,
                0,
                0,
                0,
            ],
        )
    };
    LinuxFd::from_result(raw)
}

pub fn bind(fd: BorrowedFd<'_>, address: SocketAddrV4) -> Result<(), SyscallError> {
    socket_address_call(abi::BIND, fd, address)
}

pub fn listen(fd: BorrowedFd<'_>, backlog: i32) -> Result<(), SyscallError> {
    decode_zero(unsafe {
        abi::call(
            abi::LISTEN,
            [fd.as_raw_fd() as usize, backlog as usize, 0, 0, 0, 0],
        )
    })
}

pub fn connect(fd: BorrowedFd<'_>, address: SocketAddrV4) -> Result<(), SyscallError> {
    socket_address_call(abi::CONNECT, fd, address)
}

fn socket_address_call(
    number: usize,
    fd: BorrowedFd<'_>,
    address: SocketAddrV4,
) -> Result<(), SyscallError> {
    let native = SockaddrIn::from(address);
    decode_zero(unsafe {
        abi::call(
            number,
            [
                fd.as_raw_fd() as usize,
                (&native as *const SockaddrIn) as usize,
                size_of::<SockaddrIn>(),
                0,
                0,
                0,
            ],
        )
    })
}

/// Returns a new connected descriptor. Native accept does not set CLOEXEC.
/// Prefer `accept4` when the descriptor should stay private across exec.
pub fn accept(fd: BorrowedFd<'_>) -> Result<LinuxFd, SyscallError> {
    let raw = unsafe { abi::call(abi::ACCEPT, [fd.as_raw_fd() as usize, 0, 0, 0, 0, 0]) };
    LinuxFd::from_result(raw)
}

pub fn accept4(fd: BorrowedFd<'_>) -> Result<LinuxFd, SyscallError> {
    let raw = unsafe {
        abi::call(
            abi::ACCEPT4,
            [fd.as_raw_fd() as usize, 0, 0, O_CLOEXEC as usize, 0, 0],
        )
    };
    LinuxFd::from_result(raw)
}

pub fn getsockname(fd: BorrowedFd<'_>) -> Result<SocketAddrV4, SyscallError> {
    socket_name_call(abi::GETSOCKNAME, fd)
}

pub fn getpeername(fd: BorrowedFd<'_>) -> Result<SocketAddrV4, SyscallError> {
    socket_name_call(abi::GETPEERNAME, fd)
}

fn socket_name_call(number: usize, fd: BorrowedFd<'_>) -> Result<SocketAddrV4, SyscallError> {
    let mut address = SockaddrIn::default();
    let mut len = size_of::<SockaddrIn>() as u32;
    let raw = unsafe {
        abi::call(
            number,
            [
                fd.as_raw_fd() as usize,
                (&mut address as *mut SockaddrIn) as usize,
                (&mut len as *mut u32) as usize,
                0,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)?;
    address.public_address(len)
}

/// Sends bytes on a connected stream. Uses MSG_NOSIGNAL so EPIPE is an errno
/// even on processes that use the default SIGPIPE disposition.
pub fn sendto(fd: BorrowedFd<'_>, buffer: &[u8]) -> Result<usize, SyscallError> {
    let raw = unsafe {
        abi::call(
            abi::SENDTO,
            [
                fd.as_raw_fd() as usize,
                buffer.as_ptr() as usize,
                buffer.len(),
                MSG_NOSIGNAL,
                0,
                0,
            ],
        )
    };
    decode_write(raw, buffer.len())
}

/// Receives stream bytes with default message flags and no address result.
pub fn recvfrom(fd: BorrowedFd<'_>, buffer: &mut [u8]) -> Result<ReadOutcome, SyscallError> {
    let raw = unsafe {
        abi::call(
            abi::RECVFROM,
            [
                fd.as_raw_fd() as usize,
                buffer.as_mut_ptr() as usize,
                buffer.len(),
                0,
                0,
                0,
            ],
        )
    };
    decode_read(raw, buffer.len())
}

#[repr(i32)]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Shutdown {
    Read = 0,
    Write = 1,
    Both = 2,
}

pub fn shutdown(fd: BorrowedFd<'_>, direction: Shutdown) -> Result<(), SyscallError> {
    decode_zero(unsafe {
        abi::call(
            abi::SHUTDOWN,
            [fd.as_raw_fd() as usize, direction as usize, 0, 0, 0, 0],
        )
    })
}
