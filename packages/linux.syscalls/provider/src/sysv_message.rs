use super::{abi, decode_nonnegative, decode_zero, SyscallError};
use std::fmt;

const MSGGET: usize = 68;
const MSGSND: usize = 69;
const MSGRCV: usize = 70;
const MSGCTL: usize = 71;
const IPC_PRIVATE: usize = 0;
const IPC_RMID: usize = 0;
const IPC_NOWAIT: usize = 0o4000;
const MSG_NOERROR: usize = 0o10000;
const MAX_MESSAGE_BYTES: usize = 8192;

/// Owns a newly allocated System V queue. No other package operation accepts
/// the underlying numeric identifier. Drop attempts IPC_RMID once.
#[derive(Debug)]
pub struct SysvMessageQueue(i32);

impl Drop for SysvMessageQueue {
    fn drop(&mut self) {
        let _ = remove(self.0);
    }
}

/// Allocates a fresh IPC_PRIVATE queue with owner-only permissions (0600).
pub fn msgget() -> Result<SysvMessageQueue, SyscallError> {
    let raw = unsafe { abi::invoke(MSGGET, [IPC_PRIVATE, 0o600, 0, 0, 0, 0]) };
    let id =
        i32::try_from(decode_nonnegative(raw)?).map_err(|_| SyscallError::UnexpectedReturn(raw))?;
    Ok(SysvMessageQueue(id))
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct MessageType(i64);

impl MessageType {
    pub fn new(value: i64) -> Result<Self, SyscallError> {
        if value <= 0 {
            return Err(SyscallError::InvalidInput("message type must be positive"));
        }
        Ok(Self(value))
    }

    pub fn value(self) -> i64 {
        self.0
    }
}

#[repr(C)]
struct NativeMessage {
    message_type: i64,
    payload: [u8; MAX_MESSAGE_BYTES],
}

const _: () = {
    assert!(std::mem::size_of::<NativeMessage>() == 8 + MAX_MESSAGE_BYTES);
    assert!(std::mem::align_of::<NativeMessage>() == 8);
    assert!(std::mem::offset_of!(NativeMessage, payload) == 8);
};

fn check_capacity(length: usize) -> Result<(), SyscallError> {
    if length > MAX_MESSAGE_BYTES {
        return Err(SyscallError::InvalidInput(
            "message payload exceeds 8192 bytes",
        ));
    }
    Ok(())
}

/// Sends a complete message without waiting for queue space. Linux may
/// impose a lower configured message size or queue capacity.
pub fn msgsnd(
    queue: &SysvMessageQueue,
    message_type: MessageType,
    payload: &[u8],
) -> Result<(), SyscallError> {
    check_capacity(payload.len())?;
    let mut message = NativeMessage {
        message_type: message_type.0,
        payload: [0; MAX_MESSAGE_BYTES],
    };
    message.payload[..payload.len()].copy_from_slice(payload);
    let raw = unsafe {
        abi::invoke(
            MSGSND,
            [
                queue.0 as usize,
                (&message as *const NativeMessage) as usize,
                payload.len(),
                IPC_NOWAIT,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum MessageSelection {
    First,
    Exact(MessageType),
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum MessageReceiveMode {
    RequireFit,
    Truncate,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ReceivedSysvMessage {
    pub message_type: MessageType,
    pub copied: usize,
}

/// Consumes the first matching message without waiting. RequireFit leaves an
/// overlong message queued and yields E2BIG. Truncate discards bytes beyond
/// the destination. A full destination alone does not establish truncation.
/// The destination suffix past the returned count is preserved.
pub fn msgrcv(
    queue: &SysvMessageQueue,
    selection: MessageSelection,
    mode: MessageReceiveMode,
    output: &mut [u8],
) -> Result<ReceivedSysvMessage, SyscallError> {
    check_capacity(output.len())?;
    let wanted = match selection {
        MessageSelection::First => 0,
        MessageSelection::Exact(message_type) => message_type.0 as usize,
    };
    let flags = match mode {
        MessageReceiveMode::RequireFit => IPC_NOWAIT,
        MessageReceiveMode::Truncate => IPC_NOWAIT | MSG_NOERROR,
    };
    let mut message = NativeMessage {
        message_type: 0,
        payload: [0; MAX_MESSAGE_BYTES],
    };
    let raw = unsafe {
        abi::invoke(
            MSGRCV,
            [
                queue.0 as usize,
                (&mut message as *mut NativeMessage) as usize,
                output.len(),
                wanted,
                flags,
                0,
            ],
        )
    };
    let copied = decode_nonnegative(raw)?;
    if copied > output.len() || message.message_type <= 0 {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    output[..copied].copy_from_slice(&message.payload[..copied]);
    Ok(ReceivedSysvMessage {
        message_type: MessageType(message.message_type),
        copied,
    })
}

#[derive(Debug)]
pub struct QueueRemovalError {
    error: SyscallError,
    queue: SysvMessageQueue,
}

impl QueueRemovalError {
    pub fn into_parts(self) -> (SyscallError, SysvMessageQueue) {
        (self.error, self.queue)
    }
}

impl fmt::Display for QueueRemovalError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "msgctl IPC_RMID: {}", self.error)
    }
}

impl std::error::Error for QueueRemovalError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        Some(&self.error)
    }
}

/// Removes the owned queue and discards queued messages. A failed release
/// returns the owner in the error, allowing an explicit retry or drop.
pub fn msgctl(queue: SysvMessageQueue) -> Result<(), QueueRemovalError> {
    match remove(queue.0) {
        Ok(()) => {
            std::mem::forget(queue);
            Ok(())
        }
        Err(error) => Err(QueueRemovalError { error, queue }),
    }
}

fn remove(id: i32) -> Result<(), SyscallError> {
    decode_zero(unsafe { abi::invoke(MSGCTL, [id as usize, IPC_RMID, 0, 0, 0, 0]) })
}

#[cfg(test)]
mod tests {
    use super::{msgctl, msgget, remove};
    use crate::EINVAL;

    #[test]
    fn private_queue_drop_removes_owned_kernel_object() {
        let first = msgget().unwrap();
        let second = msgget().unwrap();
        let first_id = first.0;
        let second_id = second.0;
        assert_ne!(first_id, second_id);
        drop(first);
        msgctl(second).unwrap();
        for id in [first_id, second_id] {
            let error = remove(id).unwrap_err();
            assert!(error.is_errno(EINVAL) || error.is_errno(43)); // EIDRM
        }
    }
}
