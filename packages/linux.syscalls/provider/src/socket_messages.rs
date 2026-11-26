use super::{
    abi, decode_nonnegative, decode_read, decode_write, Datagram4, ReadOutcome, SyscallError,
    UdpSocket4,
};
use crate::socket::SockaddrIn;
use std::io::{IoSlice, IoSliceMut};
use std::mem::{align_of, offset_of, size_of};
use std::net::SocketAddrV4;
use std::os::fd::{AsFd, AsRawFd, BorrowedFd};

const SENDMSG: usize = 46;
const RECVMSG: usize = 47;
const MAX_IOVECS: usize = 1024;
const MSG_CTRUNC: u32 = 0x8;
const MSG_TRUNC: u32 = 0x20;
const MSG_NOSIGNAL: usize = 0x4000;

#[repr(C)]
#[derive(Default)]
struct MessageHeader {
    name: usize,
    name_len: i32,
    name_padding: u32,
    vectors: usize,
    vectors_len: usize,
    control: usize,
    control_len: usize,
    flags: u32,
    flags_padding: u32,
}

const _: () = {
    assert!(size_of::<MessageHeader>() == 56);
    assert!(align_of::<MessageHeader>() == 8);
    assert!(offset_of!(MessageHeader, name_len) == 8);
    assert!(offset_of!(MessageHeader, vectors) == 16);
    assert!(offset_of!(MessageHeader, vectors_len) == 24);
    assert!(offset_of!(MessageHeader, control) == 32);
    assert!(offset_of!(MessageHeader, control_len) == 40);
    assert!(offset_of!(MessageHeader, flags) == 48);
    assert!(size_of::<IoSlice<'_>>() == 16);
    assert!(align_of::<IoSlice<'_>>() == 8);
    assert!(size_of::<IoSliceMut<'_>>() == 16);
    assert!(align_of::<IoSliceMut<'_>>() == 8);
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ReceivedStreamMessage {
    pub outcome: ReadOutcome,
    pub data_truncated: bool,
    pub control_truncated: bool,
    /// Kernel output bits outside the bounded data and control truncation profile.
    pub unsupported_flags: u32,
}

impl ReceivedStreamMessage {
    fn from_result(outcome: ReadOutcome, flags: u32) -> Self {
        Self {
            outcome,
            data_truncated: flags & MSG_TRUNC != 0,
            control_truncated: flags & MSG_CTRUNC != 0,
            unsupported_flags: flags & !(MSG_TRUNC | MSG_CTRUNC),
        }
    }
}

fn vector_capacity(
    mut lengths: impl ExactSizeIterator<Item = usize>,
) -> Result<usize, SyscallError> {
    if lengths.len() > MAX_IOVECS {
        return Err(SyscallError::InvalidInput(
            "message has more than 1024 I/O vectors",
        ));
    }
    lengths.try_fold(0_usize, |total, len| {
        total
            .checked_add(len)
            .filter(|size| *size <= isize::MAX as usize)
            .ok_or(SyscallError::InvalidInput(
                "message byte count exceeds isize",
            ))
    })
}

/// Sends ordered vector bytes on a connected Unix or IPv4 stream socket.
/// Supplies neither a destination name nor control data and suppresses SIGPIPE.
/// A successful short count leaves the remaining bytes for the caller.
pub fn sendmsg(fd: BorrowedFd<'_>, buffers: &[IoSlice<'_>]) -> Result<usize, SyscallError> {
    let requested = vector_capacity(buffers.iter().map(|buffer| buffer.len()))?;
    let header = MessageHeader {
        vectors: buffers.as_ptr() as usize,
        vectors_len: buffers.len(),
        ..MessageHeader::default()
    };
    // Rust guarantees Unix IoSlice ABI compatibility with C iovec. The
    // vectors and their immutable buffers remain live for the syscall.
    let raw = unsafe {
        abi::invoke(
            SENDMSG,
            [
                fd.as_raw_fd() as usize,
                (&header as *const MessageHeader) as usize,
                MSG_NOSIGNAL,
                0,
                0,
                0,
            ],
        )
    };
    decode_write(raw, requested)
}

/// Receives ordered vector bytes from a connected Unix or IPv4 stream.
/// Control data is discarded by the kernel because no control buffer is
/// supplied. MSG_CTRUNC makes that loss visible alongside any byte progress.
pub fn recvmsg(
    fd: BorrowedFd<'_>,
    buffers: &mut [IoSliceMut<'_>],
) -> Result<ReceivedStreamMessage, SyscallError> {
    let requested = vector_capacity(buffers.iter().map(|buffer| buffer.len()))?;
    let mut header = MessageHeader {
        vectors: buffers.as_mut_ptr() as usize,
        vectors_len: buffers.len(),
        ..MessageHeader::default()
    };
    // Rust guarantees Unix IoSliceMut ABI compatibility with C iovec. Each
    // destination slice stays exclusively borrowed for the syscall.
    let raw = unsafe {
        abi::invoke(
            RECVMSG,
            [
                fd.as_raw_fd() as usize,
                (&mut header as *mut MessageHeader) as usize,
                0,
                0,
                0,
                0,
            ],
        )
    };
    Ok(ReceivedStreamMessage::from_result(
        decode_read(raw, requested)?,
        header.flags,
    ))
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ReceivedDatagramMessage4 {
    pub datagram: Datagram4,
    pub data_truncated: bool,
    pub control_truncated: bool,
    /// Kernel output bits outside the bounded data and control truncation profile.
    pub unsupported_flags: u32,
}

/// Send one datagram to the supplied IPv4 peer using ordered vector bytes.
/// Supplies no control data. Success accepts the complete packet into the
/// network stack, including a successful empty packet when no bytes are given.
pub fn sendmsg_udp4(
    socket: &UdpSocket4,
    buffers: &[IoSlice<'_>],
    peer: SocketAddrV4,
) -> Result<usize, SyscallError> {
    let requested = vector_capacity(buffers.iter().map(|buffer| buffer.len()))?;
    let address = SockaddrIn::from(peer);
    let header = MessageHeader {
        name: (&address as *const SockaddrIn) as usize,
        name_len: size_of::<SockaddrIn>() as i32,
        vectors: buffers.as_ptr() as usize,
        vectors_len: buffers.len(),
        ..MessageHeader::default()
    };
    // The native address and iovecs remain live and read-only for this call.
    let raw = unsafe {
        abi::invoke(
            SENDMSG,
            [
                socket.as_fd().as_raw_fd() as usize,
                (&header as *const MessageHeader) as usize,
                MSG_NOSIGNAL,
                0,
                0,
                0,
            ],
        )
    };
    let accepted = decode_nonnegative(raw)?;
    if accepted != requested {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    Ok(accepted)
}

/// Receive one datagram into ordered writable vectors. MSG_TRUNC returns the
/// original datagram length. The initialized prefix is bounded by total
/// capacity. Zero length denotes a successful empty datagram.
pub fn recvmsg_udp4(
    socket: &UdpSocket4,
    buffers: &mut [IoSliceMut<'_>],
) -> Result<ReceivedDatagramMessage4, SyscallError> {
    let capacity = vector_capacity(buffers.iter().map(|buffer| buffer.len()))?;
    let mut address = SockaddrIn::default();
    let mut header = MessageHeader {
        name: (&mut address as *mut SockaddrIn) as usize,
        name_len: size_of::<SockaddrIn>() as i32,
        vectors: buffers.as_mut_ptr() as usize,
        vectors_len: buffers.len(),
        ..MessageHeader::default()
    };
    // The kernel receives only the typed name storage and exclusive byte
    // slices. No control buffer is available to receive ancillary data.
    let raw = unsafe {
        abi::invoke(
            RECVMSG,
            [
                socket.as_fd().as_raw_fd() as usize,
                (&mut header as *mut MessageHeader) as usize,
                MSG_TRUNC as usize,
                0,
                0,
                0,
            ],
        )
    };
    let datagram_len = decode_nonnegative(raw)?;
    let peer = address
        .public_address(header.name_len as u32)
        .map_err(|_| SyscallError::UnexpectedReturn(raw))?;
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
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn message_flags_preserve_unknown_bits_and_do_not_replace_progress() {
        let message = ReceivedStreamMessage::from_result(
            ReadOutcome::Progress(2),
            0x80 | MSG_TRUNC | MSG_CTRUNC,
        );
        assert_eq!(message.outcome, ReadOutcome::Progress(2));
        assert!(message.data_truncated);
        assert!(message.control_truncated);
        assert_eq!(message.unsupported_flags, 0x80);
    }
}
