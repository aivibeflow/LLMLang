//! Native Linux POSIX message queues with owned descriptors and bounded buffers.

use super::posix_timer::NativeSignalEvent;
use super::{
    abi, close, decode_write, decode_zero, LinuxFd, SyscallError, Timespec, O_CREAT, O_EXCL,
    O_NONBLOCK,
};
use std::ffi::CStr;
use std::os::fd::{AsFd, AsRawFd, BorrowedFd};
use std::ptr;

const MQ_OPEN: usize = 240;
const MQ_UNLINK: usize = 241;
const MQ_TIMEDSEND: usize = 242;
const MQ_TIMEDRECEIVE: usize = 243;
const MQ_NOTIFY: usize = 244;
const MQ_GETSETATTR: usize = 245;
const MQ_PRIO_MAX: u32 = 32_768;
const NAME_MAX: usize = 255;

/// A POSIX queue name consists of `/` followed by one nonempty component.
#[derive(Clone, Copy, Debug)]
pub struct QueueName<'a>(&'a CStr);

impl<'a> QueueName<'a> {
    pub fn new(name: &'a CStr) -> Result<Self, SyscallError> {
        let Some(component) = name.to_bytes().strip_prefix(b"/") else {
            return Err(SyscallError::InvalidInput(
                "message queue name must start with '/'",
            ));
        };
        if component.is_empty()
            || component.len() > NAME_MAX
            || component.contains(&b'/')
            || component == b"."
            || component == b".."
        {
            return Err(SyscallError::InvalidInput(
                "invalid message queue name component",
            ));
        }
        Ok(Self(name))
    }

    fn argument(self) -> usize {
        // The native syscall takes the POSIX name without its leading slash.
        self.0.to_bytes_with_nul()[1..].as_ptr() as usize
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(i32)]
pub enum QueueAccess {
    ReadOnly = 0,
    WriteOnly = 1,
    ReadWrite = 2,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct QueueLimits {
    max_messages: usize,
    max_message_size: usize,
}

impl QueueLimits {
    pub fn new(max_messages: usize, max_message_size: usize) -> Result<Self, SyscallError> {
        let valid = 1..=i64::MAX as usize;
        if !valid.contains(&max_messages) || !valid.contains(&max_message_size) {
            return Err(SyscallError::InvalidInput(
                "queue limits must fit positive Linux longs",
            ));
        }
        Ok(Self {
            max_messages,
            max_message_size,
        })
    }

    pub fn max_messages(self) -> usize {
        self.max_messages
    }

    pub fn max_message_size(self) -> usize {
        self.max_message_size
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct QueueCreate {
    pub permissions: u16,
    pub exclusive: bool,
    pub limits: Option<QueueLimits>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct QueueOpen {
    pub access: QueueAccess,
    pub nonblocking: bool,
    pub create: Option<QueueCreate>,
}

#[derive(Debug)]
pub struct MessageQueue(LinuxFd);

impl MessageQueue {
    /// Release the descriptor. A separately named queue remains accessible
    /// until its name is unlinked.
    pub fn close(self) -> Result<(), SyscallError> {
        close(self.0)
    }
}

impl AsFd for MessageQueue {
    fn as_fd(&self) -> BorrowedFd<'_> {
        self.0.as_fd()
    }
}

#[repr(C)]
#[derive(Default)]
struct NativeQueueAttributes {
    flags: i64,
    max_messages: i64,
    max_message_size: i64,
    messages: i64,
    reserved: [i64; 4],
}

const _: () = {
    assert!(std::mem::size_of::<NativeQueueAttributes>() == 64);
    assert!(std::mem::align_of::<NativeQueueAttributes>() == 8);
    assert!(std::mem::offset_of!(NativeQueueAttributes, max_messages) == 8);
    assert!(std::mem::offset_of!(NativeQueueAttributes, max_message_size) == 16);
    assert!(std::mem::offset_of!(NativeQueueAttributes, messages) == 24);
    assert!(std::mem::offset_of!(NativeQueueAttributes, reserved) == 32);
};

impl From<QueueLimits> for NativeQueueAttributes {
    fn from(limits: QueueLimits) -> Self {
        Self {
            max_messages: limits.max_messages as i64,
            max_message_size: limits.max_message_size as i64,
            ..Self::default()
        }
    }
}

/// Opens or creates a named queue and receives one CLOEXEC descriptor.
/// Creation permissions are masked by the process umask. Additional limits
/// on message count and size are enforced by the current IPC namespace.
pub fn mq_open(name: QueueName<'_>, options: QueueOpen) -> Result<MessageQueue, SyscallError> {
    let mut flags = options.access as i32;
    if options.nonblocking {
        flags |= O_NONBLOCK;
    }
    let mut mode = 0;
    let mut attributes = None;
    if let Some(creation) = options.create {
        if creation.permissions > 0o777 {
            return Err(SyscallError::InvalidInput(
                "queue mode must contain only permission bits",
            ));
        }
        flags |= O_CREAT;
        if creation.exclusive {
            flags |= O_EXCL;
        }
        mode = creation.permissions;
        attributes = creation.limits.map(NativeQueueAttributes::from);
    }
    let raw = unsafe {
        abi::invoke(
            MQ_OPEN,
            [
                name.argument(),
                flags as usize,
                mode as usize,
                address(attributes.as_ref()),
                0,
                0,
            ],
        )
    };
    Ok(MessageQueue(LinuxFd::from_result(raw)?))
}

/// Removes the name. Open queue descriptors remain valid until closed.
pub fn mq_unlink(name: QueueName<'_>) -> Result<(), SyscallError> {
    decode_zero(unsafe { abi::invoke(MQ_UNLINK, [name.argument(), 0, 0, 0, 0, 0]) })
}

/// Sends one complete message. The optional deadline is absolute CLOCK_REALTIME.
pub fn mq_timedsend(
    queue: &MessageQueue,
    message: &[u8],
    priority: u32,
    deadline: Option<Timespec>,
) -> Result<(), SyscallError> {
    let raw = unsafe {
        abi::invoke(
            MQ_TIMEDSEND,
            [
                queue.0.as_raw_fd() as usize,
                message.as_ptr() as usize,
                message.len(),
                priority as usize,
                address(deadline.as_ref()),
                0,
            ],
        )
    };
    decode_zero(raw)
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ReceivedMessage {
    pub length: usize,
    pub priority: u32,
}

/// Receives one message, including an empty message. The kernel requires the
/// buffer to accommodate the queue's maximum message size. The returned length
/// identifies the received prefix. The optional deadline is absolute CLOCK_REALTIME.
pub fn mq_timedreceive(
    queue: &MessageQueue,
    buffer: &mut [u8],
    deadline: Option<Timespec>,
) -> Result<ReceivedMessage, SyscallError> {
    let mut priority = MQ_PRIO_MAX;
    let raw = unsafe {
        abi::invoke(
            MQ_TIMEDRECEIVE,
            [
                queue.0.as_raw_fd() as usize,
                buffer.as_mut_ptr() as usize,
                buffer.len(),
                ptr::from_mut(&mut priority) as usize,
                address(deadline.as_ref()),
                0,
            ],
        )
    };
    let length = decode_write(raw, buffer.len())?;
    if priority >= MQ_PRIO_MAX {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    Ok(ReceivedMessage { length, priority })
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct QueueAttributes {
    pub nonblocking: bool,
    pub limits: QueueLimits,
    pub messages: usize,
}

/// Returns the previous attributes, optionally changing O_NONBLOCK on the open
/// file description. Queue limits and message contents are unchanged.
pub fn mq_getsetattr(
    queue: &MessageQueue,
    nonblocking: Option<bool>,
) -> Result<QueueAttributes, SyscallError> {
    let update = nonblocking.map(|enabled| NativeQueueAttributes {
        flags: if enabled { O_NONBLOCK as i64 } else { 0 },
        ..NativeQueueAttributes::default()
    });
    let mut previous = NativeQueueAttributes::default();
    let raw = unsafe {
        abi::invoke(
            MQ_GETSETATTR,
            [
                queue.0.as_raw_fd() as usize,
                address(update.as_ref()),
                ptr::from_mut(&mut previous) as usize,
                0,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)?;
    if previous.flags & !(O_NONBLOCK as i64) != 0
        || previous.max_messages <= 0
        || previous.max_message_size <= 0
        || !(0..=previous.max_messages).contains(&previous.messages)
    {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    Ok(QueueAttributes {
        nonblocking: previous.flags != 0,
        limits: QueueLimits {
            max_messages: previous.max_messages as usize,
            max_message_size: previous.max_message_size as usize,
        },
        messages: previous.messages as usize,
    })
}

fn address<T>(value: Option<&T>) -> usize {
    value.map_or(ptr::null(), ptr::from_ref) as usize
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum QueueNotification {
    RegisterNone,
    Unregister,
}

/// Register a thread-group-owned SIGEV_NONE notification or unregister it.
/// Registration is one-shot and does not send a signal or run a callback.
/// Linux reports EBUSY when a registration is already present and silently
/// accepts unregister attempts by a group that does not own the registration.
pub fn mq_notify(queue: &MessageQueue, action: QueueNotification) -> Result<(), SyscallError> {
    let event = NativeSignalEvent::none();
    let input = match action {
        QueueNotification::RegisterNone => ptr::from_ref(&event) as usize,
        QueueNotification::Unregister => 0,
    };
    decode_zero(unsafe {
        abi::invoke(
            MQ_NOTIFY,
            [queue.as_fd().as_raw_fd() as usize, input, 0, 0, 0, 0],
        )
    })
}
