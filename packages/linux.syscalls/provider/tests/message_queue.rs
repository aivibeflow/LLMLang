use linux_syscalls_provider::*;
use std::ffi::CString;
use std::os::fd::AsFd;
use std::sync::atomic::{AtomicUsize, Ordering};

const ENOENT: i32 = 2;
const EEXIST: i32 = 17;
const EMSGSIZE: i32 = 90;
const ETIMEDOUT: i32 = 110;
const BUFFER_LENGTH: usize = 16;

struct QueueFixture {
    name: Option<CString>,
    queue: MessageQueue,
}

impl QueueFixture {
    fn new(max_messages: usize, nonblocking: bool) -> Self {
        static NEXT_NAME: AtomicUsize = AtomicUsize::new(0);
        let limits = QueueLimits::new(max_messages, BUFFER_LENGTH).unwrap();
        let options = QueueOpen {
            access: QueueAccess::ReadWrite,
            nonblocking,
            create: Some(QueueCreate {
                permissions: 0o600,
                exclusive: true,
                limits: Some(limits),
            }),
        };
        for _ in 0..32 {
            let serial = NEXT_NAME.fetch_add(1, Ordering::Relaxed);
            let name =
                CString::new(format!("/llmlang-mq-{}-{serial}", std::process::id())).unwrap();
            match mq_open(QueueName::new(&name).unwrap(), options) {
                Ok(queue) => {
                    return Self {
                        name: Some(name),
                        queue,
                    }
                }
                Err(error) if error.is_errno(EEXIST) => continue,
                Err(error) => panic!("create isolated Linux message queue: {error}"),
            }
        }
        panic!("could not allocate a unique queue name");
    }

    fn name(&self) -> QueueName<'_> {
        QueueName::new(self.name.as_deref().expect("queue still linked")).unwrap()
    }

    fn unlink(&mut self) {
        mq_unlink(self.name()).unwrap();
        self.name = None;
    }
}

impl Drop for QueueFixture {
    fn drop(&mut self) {
        if let Some(name) = self.name.as_deref() {
            let _ = mq_unlink(QueueName::new(name).expect("fixture name is valid"));
        }
    }
}

#[test]
fn queue_transfers_typed_messages_in_priority_order() {
    let fixture = QueueFixture::new(3, true);
    let queue = &fixture.queue;
    assert_eq!(fcntl_getfd(queue.as_fd()).unwrap() & 1, 1);
    mq_timedsend(queue, b"one", 1, None).unwrap();
    mq_timedsend(queue, b"two\x00", 7, None).unwrap();
    mq_timedsend(queue, b"", 7, None).unwrap();
    assert_eq!(mq_getsetattr(queue, None).unwrap().messages, 3);
    assert!(mq_timedsend(queue, b"full", 1, None)
        .unwrap_err()
        .is_errno(EAGAIN));
    let mut buffer = [0xa5_u8; BUFFER_LENGTH];
    assert_eq!(
        mq_timedreceive(queue, &mut buffer, None).unwrap(),
        ReceivedMessage {
            length: 4,
            priority: 7
        }
    );
    assert_eq!(&buffer[..4], b"two\x00");
    assert!(buffer[4..].iter().all(|byte| *byte == 0xa5));
    let previous = buffer;
    assert_eq!(
        mq_timedreceive(queue, &mut buffer, None).unwrap(),
        ReceivedMessage {
            length: 0,
            priority: 7
        }
    );
    assert_eq!(buffer, previous);
    assert_eq!(
        mq_timedreceive(queue, &mut buffer, None).unwrap(),
        ReceivedMessage {
            length: 3,
            priority: 1
        }
    );
    assert_eq!(&buffer[..3], b"one");
    assert!(mq_timedreceive(queue, &mut buffer, None)
        .unwrap_err()
        .is_errno(EAGAIN));
}

#[test]
fn queue_timeouts_flags_and_unlink_preserve_owned_descriptor() {
    let mut fixture = QueueFixture::new(1, false);
    let original_name = fixture.name.as_ref().unwrap().clone();
    let options = QueueOpen {
        access: QueueAccess::ReadOnly,
        nonblocking: false,
        create: None,
    };
    let second = mq_open(QueueName::new(&original_name).unwrap(), options).unwrap();
    let mut buffer = [0_u8; BUFFER_LENGTH];
    let elapsed = Some(Timespec::default());
    assert!(mq_timedreceive(&fixture.queue, &mut buffer, elapsed)
        .unwrap_err()
        .is_errno(ETIMEDOUT));
    assert!(
        !mq_getsetattr(&fixture.queue, Some(true))
            .unwrap()
            .nonblocking
    );
    assert!(mq_getsetattr(&fixture.queue, None).unwrap().nonblocking);
    assert!(!mq_getsetattr(&second, None).unwrap().nonblocking);
    assert!(mq_timedreceive(&fixture.queue, &mut buffer, elapsed)
        .unwrap_err()
        .is_errno(EAGAIN));
    assert!(
        mq_getsetattr(&fixture.queue, Some(false))
            .unwrap()
            .nonblocking
    );
    mq_timedsend(&fixture.queue, b"held", 1, elapsed).unwrap();
    assert!(mq_timedsend(&fixture.queue, b"full", 1, elapsed)
        .unwrap_err()
        .is_errno(ETIMEDOUT));

    fixture.unlink();
    let former = QueueName::new(&original_name).unwrap();
    assert!(mq_open(former, options).unwrap_err().is_errno(ENOENT));
    assert!(mq_unlink(former).unwrap_err().is_errno(ENOENT));
    let received = mq_timedreceive(&second, &mut buffer, elapsed).unwrap();
    assert_eq!(&buffer[..received.length], b"held");
    second.close().unwrap();
}

#[test]
fn queue_inputs_validate_names_sizes_and_kernel_errors() {
    for name in [c"", c"relative", c"/", c"//queue", c"/a/b", c"/.", c"/.."] {
        assert!(matches!(
            QueueName::new(name),
            Err(SyscallError::InvalidInput(_))
        ));
    }
    let oversized = CString::new(format!("/{}", "x".repeat(256))).unwrap();
    assert!(QueueName::new(&oversized).is_err());
    assert!(QueueLimits::new(0, BUFFER_LENGTH).is_err());
    assert!(QueueLimits::new(1, usize::MAX).is_err());

    let fixture = QueueFixture::new(2, true);
    let queue = &fixture.queue;
    let limits = QueueLimits::new(2, BUFFER_LENGTH).unwrap();
    let create = QueueCreate {
        permissions: 0o600,
        exclusive: true,
        limits: Some(limits),
    };
    let options = QueueOpen {
        access: QueueAccess::ReadOnly,
        nonblocking: true,
        create: Some(create),
    };
    assert!(mq_open(fixture.name(), options)
        .unwrap_err()
        .is_errno(EEXIST));
    let invalid = QueueOpen {
        create: Some(QueueCreate {
            permissions: 0o1000,
            ..create
        }),
        ..options
    };
    assert!(matches!(
        mq_open(fixture.name(), invalid),
        Err(SyscallError::InvalidInput(_))
    ));
    assert_eq!(mq_getsetattr(queue, None).unwrap().limits, limits);
    assert!(mq_timedsend(queue, &[0; BUFFER_LENGTH + 1], 0, None)
        .unwrap_err()
        .is_errno(EMSGSIZE));
    assert!(mq_timedsend(queue, b"priority", 32_768, None)
        .unwrap_err()
        .is_errno(EINVAL));
    mq_timedsend(queue, b"x", 32_767, None).unwrap();
    assert!(mq_timedreceive(queue, &mut [0; BUFFER_LENGTH - 1], None)
        .unwrap_err()
        .is_errno(EMSGSIZE));
    assert_eq!(mq_getsetattr(queue, None).unwrap().messages, 1);
    let mut bytes = [0; BUFFER_LENGTH];
    assert_eq!(
        mq_timedreceive(queue, &mut bytes, None).unwrap(),
        ReceivedMessage {
            length: 1,
            priority: 32_767
        }
    );
    assert_eq!(bytes[0], b'x');
}

#[test]
fn queue_notify_none_owns_one_shot_registration_and_tears_down() {
    const CHILD_QUEUE: &str = "LLMLANG_MQ_NOTIFY_CHILD_QUEUE";
    const TEST_NAME: &str = "queue_notify_none_owns_one_shot_registration_and_tears_down";
    const EBUSY: i32 = 16;

    let notification = QueueNotification::RegisterNone;
    let unregister = QueueNotification::Unregister;
    let options = QueueOpen {
        access: QueueAccess::ReadOnly,
        nonblocking: true,
        create: None,
    };
    if let Some(name) = std::env::var_os(CHILD_QUEUE) {
        use std::os::unix::ffi::OsStrExt;
        let name = CString::new(name.as_bytes()).unwrap();
        let queue = mq_open(QueueName::new(&name).unwrap(), options).unwrap();
        mq_notify(&queue, unregister).unwrap();
        assert!(mq_notify(&queue, notification).unwrap_err().is_errno(EBUSY));
        queue.close().unwrap();
        return;
    }

    let fixture = QueueFixture::new(2, true);
    let queue = &fixture.queue;
    mq_notify(queue, notification).unwrap();
    assert!(mq_notify(queue, notification).unwrap_err().is_errno(EBUSY));
    let output = std::process::Command::new(std::env::current_exe().unwrap())
        .args(["--exact", TEST_NAME])
        .env(
            CHILD_QUEUE,
            fixture.name.as_ref().unwrap().to_str().unwrap(),
        )
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stdout)
    );
    assert!(mq_notify(queue, notification).unwrap_err().is_errno(EBUSY));

    mq_notify(queue, unregister).unwrap();
    mq_notify(queue, notification).unwrap();
    mq_timedsend(queue, b"first", 0, None).unwrap();
    mq_notify(queue, notification).unwrap();
    mq_timedsend(queue, b"second", 0, None).unwrap();
    assert!(mq_notify(queue, notification).unwrap_err().is_errno(EBUSY));

    let other = mq_open(fixture.name(), options).unwrap();
    other.close().unwrap();
    mq_notify(queue, notification).unwrap();
    mq_notify(queue, unregister).unwrap();
}
