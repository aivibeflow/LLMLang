//! Native x86-64 message batches for the typed IPv4 UDP socket profile.

use crate::socket::SockaddrIn;
use crate::{
    abi, decode_nonnegative, Datagram4, ReceivedDatagramMessage4, SyscallError, UdpSocket4,
};
use std::io::{IoSlice, IoSliceMut};
use std::mem::{align_of, offset_of, size_of};
use std::net::SocketAddrV4;
use std::os::fd::{AsFd, AsRawFd};

const RECVMMSG: usize = 299;
const SENDMMSG: usize = 307;
const MAX_MESSAGES: usize = 32;
const MAX_VECTORS: usize = 16;
const MSG_CTRUNC: u32 = 0x8;
const MSG_TRUNC: u32 = 0x20;
const MSG_DONTWAIT: usize = 0x40;
const MSG_NOSIGNAL: usize = 0x4000;

#[repr(C)]
#[derive(Default)]
struct NativeMmsgHeader {
    name: usize,
    name_len: i32,
    name_padding: u32,
    vectors: usize,
    vector_count: usize,
    control: usize,
    control_len: usize,
    flags: u32,
    flags_padding: u32,
    message_len: u32,
    message_padding: u32,
}

const _: () = {
    assert!(size_of::<NativeMmsgHeader>() == 64);
    assert!(align_of::<NativeMmsgHeader>() == 8);
    assert!(offset_of!(NativeMmsgHeader, name_len) == 8);
    assert!(offset_of!(NativeMmsgHeader, vectors) == 16);
    assert!(offset_of!(NativeMmsgHeader, vector_count) == 24);
    assert!(offset_of!(NativeMmsgHeader, control) == 32);
    assert!(offset_of!(NativeMmsgHeader, control_len) == 40);
    assert!(offset_of!(NativeMmsgHeader, flags) == 48);
    assert!(offset_of!(NativeMmsgHeader, message_len) == 56);
    assert!(size_of::<IoSlice<'_>>() == 16 && align_of::<IoSlice<'_>>() == 8);
    assert!(size_of::<IoSliceMut<'_>>() == 16 && align_of::<IoSliceMut<'_>>() == 8);
};

impl NativeMmsgHeader {
    fn datagram(name: usize, vectors: usize, vector_count: usize) -> Self {
        Self {
            name,
            name_len: size_of::<SockaddrIn>() as i32,
            vectors,
            vector_count,
            ..Self::default()
        }
    }
}

#[derive(Clone, Copy, Debug)]
pub struct SendDatagram4<'a> {
    pub peer: SocketAddrV4,
    pub buffers: &'a [IoSlice<'a>],
}

fn check_batch_size(count: usize) -> Result<(), SyscallError> {
    if !(1..=MAX_MESSAGES).contains(&count) {
        return Err(SyscallError::InvalidInput(
            "datagram batch must have between one and 32 envelopes",
        ));
    }
    Ok(())
}

fn vector_capacity(
    mut lengths: impl ExactSizeIterator<Item = usize>,
) -> Result<usize, SyscallError> {
    if lengths.len() > MAX_VECTORS {
        return Err(SyscallError::InvalidInput(
            "batch envelope has more than 16 I/O vectors",
        ));
    }
    lengths.try_fold(0_usize, |total, len| {
        total
            .checked_add(len)
            .filter(|size| *size <= isize::MAX as usize)
            .ok_or(SyscallError::InvalidInput(
                "envelope byte count exceeds isize",
            ))
    })
}

fn completed_count(raw: isize, submitted: usize) -> Result<usize, SyscallError> {
    let count = decode_nonnegative(raw)?;
    if !(1..=submitted).contains(&count) {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    Ok(count)
}

/// Sends an ordered, nonblocking batch of vector datagrams. The result contains
/// exactly the lengths of the sent prefix. When that prefix is nonempty,
/// Linux may omit the errno responsible for leaving later messages unsent.
pub fn sendmmsg_udp4(
    socket: &UdpSocket4,
    messages: &[SendDatagram4<'_>],
) -> Result<Vec<usize>, SyscallError> {
    check_batch_size(messages.len())?;
    let expected = messages
        .iter()
        .map(|message| vector_capacity(message.buffers.iter().map(|buffer| buffer.len())))
        .collect::<Result<Vec<_>, _>>()?;
    let addresses: Vec<_> = messages
        .iter()
        .map(|message| SockaddrIn::from(message.peer))
        .collect();
    let mut headers: Vec<_> = messages
        .iter()
        .zip(&addresses)
        .map(|(message, address)| {
            NativeMmsgHeader::datagram(
                (address as *const SockaddrIn) as usize,
                message.buffers.as_ptr() as usize,
                message.buffers.len(),
            )
        })
        .collect();
    // I/O vectors and address storage remain live for the full call. Linux
    // writes one message length for each accepted datagram in the prefix.
    let raw = unsafe {
        abi::call(
            SENDMMSG,
            [
                socket.as_fd().as_raw_fd() as usize,
                headers.as_mut_ptr() as usize,
                headers.len(),
                MSG_DONTWAIT | MSG_NOSIGNAL,
                0,
                0,
            ],
        )
    };
    let completed = completed_count(raw, headers.len())?;
    if headers
        .iter()
        .zip(&expected)
        .take(completed)
        .any(|(header, len)| header.message_len as usize != *len)
    {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    Ok(headers[..completed]
        .iter()
        .map(|header| header.message_len as usize)
        .collect())
}

/// Receives an ordered, nonblocking batch of vector datagrams. Each completed
/// envelope reports source, bytes written, original length and truncation.
/// The kernel receives no control storage or timeout pointer.
pub fn recvmmsg_udp4(
    socket: &UdpSocket4,
    buffers: &mut [&mut [IoSliceMut<'_>]],
) -> Result<Vec<ReceivedDatagramMessage4>, SyscallError> {
    check_batch_size(buffers.len())?;
    let capacities = buffers
        .iter()
        .map(|vectors| vector_capacity(vectors.iter().map(|buffer| buffer.len())))
        .collect::<Result<Vec<_>, _>>()?;
    let mut addresses: Vec<_> = (0..buffers.len()).map(|_| SockaddrIn::default()).collect();
    let mut headers: Vec<_> = buffers
        .iter_mut()
        .zip(&mut addresses)
        .map(|(vectors, address)| {
            NativeMmsgHeader::datagram(
                (address as *mut SockaddrIn) as usize,
                vectors.as_mut_ptr() as usize,
                vectors.len(),
            )
        })
        .collect();
    // IoSliceMut uses Unix's iovec ABI and retains exclusively borrowed byte
    // slices. All vectors, names, and headers stay live until the call returns.
    let raw = unsafe {
        abi::call(
            RECVMMSG,
            [
                socket.as_fd().as_raw_fd() as usize,
                headers.as_mut_ptr() as usize,
                headers.len(),
                MSG_DONTWAIT | MSG_TRUNC as usize,
                0,
                0,
            ],
        )
    };
    let completed = completed_count(raw, headers.len())?;
    headers
        .into_iter()
        .zip(addresses)
        .zip(capacities)
        .take(completed)
        .map(|((header, address), capacity)| {
            let peer = address
                .public_address(header.name_len as u32)
                .map_err(|_| SyscallError::UnexpectedReturn(raw))?;
            let datagram_len = header.message_len as usize;
            let datagram = Datagram4 {
                peer,
                bytes_written: datagram_len.min(capacity),
                datagram_len,
            };
            let data_truncated = header.flags & MSG_TRUNC != 0;
            if data_truncated != datagram.truncated() {
                return Err(SyscallError::UnexpectedReturn(raw));
            }
            Ok(ReceivedDatagramMessage4 {
                datagram,
                data_truncated,
                control_truncated: header.flags & MSG_CTRUNC != 0,
                unsupported_flags: header.flags & !(MSG_TRUNC | MSG_CTRUNC),
            })
        })
        .collect()
}
