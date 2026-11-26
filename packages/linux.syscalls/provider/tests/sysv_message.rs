use linux_syscalls_provider::{
    msgctl, msgget, msgrcv, msgsnd, MessageReceiveMode, MessageSelection, MessageType, SyscallError,
};

#[test]
fn queue_selects_positive_types_and_preserves_order() {
    let queue = msgget().unwrap();
    let other = msgget().unwrap();
    let first = MessageType::new(1).unwrap();
    let last = MessageType::new(i64::MAX).unwrap();
    msgsnd(&queue, first, b"first").unwrap();
    msgsnd(&queue, last, b"\x00\xff").unwrap();
    msgsnd(&queue, first, b"").unwrap();

    let mut output = [0xaa; 8];
    let type_only = msgrcv(
        &queue,
        MessageSelection::Exact(last),
        MessageReceiveMode::RequireFit,
        &mut output,
    )
    .unwrap();
    assert_eq!(type_only.message_type.value(), i64::MAX);
    assert_eq!(type_only.copied, 2);
    assert_eq!(output, [0, 0xff, 0xaa, 0xaa, 0xaa, 0xaa, 0xaa, 0xaa]);

    let independent = msgrcv(
        &other,
        MessageSelection::First,
        MessageReceiveMode::RequireFit,
        &mut output,
    );
    assert!(independent.unwrap_err().is_errno(42)); // ENOMSG
    let ordered = msgrcv(
        &queue,
        MessageSelection::First,
        MessageReceiveMode::RequireFit,
        &mut output,
    )
    .unwrap();
    assert_eq!(ordered.message_type, first);
    assert_eq!(&output[..ordered.copied], b"first");
    let empty = msgrcv(
        &queue,
        MessageSelection::First,
        MessageReceiveMode::RequireFit,
        &mut [],
    )
    .unwrap();
    assert_eq!(empty.message_type, first);
    assert_eq!(empty.copied, 0);
    msgctl(other).unwrap();
    msgctl(queue).unwrap();
}

#[test]
fn queue_reports_empty_oversize_and_truncation_exactly() {
    let queue = msgget().unwrap();
    for invalid in [i64::MIN, 0] {
        assert!(matches!(
            MessageType::new(invalid),
            Err(SyscallError::InvalidInput(_))
        ));
    }
    let tag = MessageType::new(3).unwrap();
    let mut too_large = [0; 8193];
    assert!(matches!(
        msgsnd(&queue, tag, &too_large),
        Err(SyscallError::InvalidInput(_))
    ));
    assert!(matches!(
        msgrcv(
            &queue,
            MessageSelection::First,
            MessageReceiveMode::RequireFit,
            &mut too_large
        ),
        Err(SyscallError::InvalidInput(_))
    ));
    msgsnd(&queue, tag, b"12345").unwrap();
    let mut short = [0xaa; 2];
    let blocked = msgrcv(
        &queue,
        MessageSelection::First,
        MessageReceiveMode::RequireFit,
        &mut short,
    );
    assert!(blocked.unwrap_err().is_errno(7)); // E2BIG
    assert_eq!(short, [0xaa; 2]);

    let truncated = msgrcv(
        &queue,
        MessageSelection::First,
        MessageReceiveMode::Truncate,
        &mut short,
    )
    .unwrap();
    assert_eq!(truncated.message_type, tag);
    assert_eq!(truncated.copied, 2);
    assert_eq!(&short, b"12");
    let absent = msgrcv(
        &queue,
        MessageSelection::First,
        MessageReceiveMode::RequireFit,
        &mut short,
    );
    assert!(absent.unwrap_err().is_errno(42)); // ENOMSG
    msgctl(queue).unwrap();
}
