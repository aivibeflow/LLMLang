use linux_syscalls_provider::*;

#[test]
fn ordinary_io_priorities_remain_in_the_calling_thread() {
    let parent_priority = ioprio_get_current().unwrap();
    std::thread::spawn(|| {
        ioprio_set_current(IoPriority::BestEffort(3)).unwrap();
        let observed = IoPriorityObservation { class: 2, data: 3 };
        assert_eq!(ioprio_get_current().unwrap(), observed);
        assert!(matches!(
            ioprio_set_current(IoPriority::BestEffort(8)),
            Err(SyscallError::InvalidInput(_))
        ));
        assert_eq!(ioprio_get_current().unwrap(), observed);
        ioprio_set_current(IoPriority::Idle).unwrap();
        assert_eq!(ioprio_get_current().unwrap().class, 3);
        ioprio_set_current(IoPriority::Normal).unwrap();
        assert_eq!(ioprio_get_current().unwrap().class, 0);
    })
    .join()
    .unwrap();
    assert_eq!(ioprio_get_current().unwrap(), parent_priority);
}

#[test]
fn nice_setting_remains_in_the_calling_thread() {
    let parent_priority = getpriority(PriorityKind::Process, 0).unwrap();
    std::thread::spawn(|| {
        let previous = getpriority(PriorityKind::Process, 0).unwrap();
        let requested = (previous + 1).clamp(0, 19);
        setpriority_current(requested).unwrap();
        assert_eq!(getpriority(PriorityKind::Process, 0).unwrap(), requested);
        assert!(matches!(
            setpriority_current(-1),
            Err(SyscallError::InvalidInput(_))
        ));
        assert!(matches!(
            setpriority_current(20),
            Err(SyscallError::InvalidInput(_))
        ));
        assert_eq!(getpriority(PriorityKind::Process, 0).unwrap(), requested);
    })
    .join()
    .unwrap();
    assert_eq!(
        getpriority(PriorityKind::Process, 0).unwrap(),
        parent_priority
    );
}
