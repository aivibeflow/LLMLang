use linux_syscalls_provider::*;

#[test]
fn process_vm_self_copies_only_the_reported_prefix() {
    let source = [1, 127, 0, 255, 10];
    for transfer in [process_vm_readv, process_vm_writev] {
        let mut destination = [0x55; 7];
        match transfer(&source, &mut destination) {
            Ok(value) => assert_eq!(value, 5),
            Err(error) if [1, 13, 38].into_iter().any(|code| error.is_errno(code)) => {
                assert_eq!(destination, [0x55; 7]);
                continue;
            }
            Err(error) => panic!("unexpected process_vm result: {error:?}"),
        }
        assert_eq!(destination, [1, 127, 0, 255, 10, 0x55, 0x55]);

        let mut short = [0x55; 3];
        assert_eq!(transfer(&source, &mut short).unwrap(), 3);
        assert_eq!(short, [1, 127, 0]);
        assert_eq!(transfer(&[], &mut short).unwrap(), 0);
        assert_eq!(short, [1, 127, 0]);
        assert_eq!(transfer(&source, &mut []).unwrap(), 0);

        let (prefix, tail) = destination.split_at_mut(2);
        let before = [prefix[0], prefix[1]];
        assert_eq!(transfer(prefix, tail).unwrap(), 2);
        assert_eq!(&tail[..2], &before);
        assert_eq!(&tail[2..], &[10, 0x55, 0x55]);
    }
    assert_eq!(source, [1, 127, 0, 255, 10]);
}

#[test]
fn scheduler_attrs_match_independent_current_thread_observations() {
    let attributes = sched_getattr().unwrap();
    let policy = sched_getscheduler(0).unwrap();
    assert_eq!(attributes.policy, policy.code as u32);
    assert_eq!(attributes.flags & 1 != 0, policy.reset_on_fork);
    if matches!(policy.code, 0 | 3) {
        assert_eq!(
            attributes.nice,
            getpriority(PriorityKind::Process, 0).unwrap()
        );
    }
    if matches!(policy.code, 1 | 2) {
        assert_eq!(attributes.priority, sched_getparam(0).unwrap() as u32);
    }
}
