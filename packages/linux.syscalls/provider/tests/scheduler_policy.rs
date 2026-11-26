use linux_syscalls_provider::*;

#[test]
fn ordinary_scheduler_updates_change_only_the_calling_thread() {
    let parent = sched_getscheduler(0).unwrap();
    let parent_nice = getpriority(PriorityKind::Process, 0).unwrap();
    std::thread::spawn(|| {
        sched_setparam().unwrap();
        assert_eq!(sched_getparam(0).unwrap(), 0);
        sched_setscheduler(SchedulerPolicy::Batch).unwrap();
        assert_eq!(sched_getscheduler(0).unwrap().code, 3);
        let next_nice = (getpriority(PriorityKind::Process, 0).unwrap() + 1).clamp(0, 19);
        sched_setattr(SchedulerPolicy::Normal, next_nice).unwrap();
        assert_eq!(sched_getscheduler(0).unwrap().code, 0);
        assert_eq!(getpriority(PriorityKind::Process, 0).unwrap(), next_nice);
        assert!(matches!(
            sched_setattr(SchedulerPolicy::Batch, 20),
            Err(SyscallError::InvalidInput(_))
        ));
        assert_eq!(sched_getscheduler(0).unwrap().code, 0);
        sched_setscheduler(SchedulerPolicy::Idle).unwrap();
        assert_eq!(sched_getscheduler(0).unwrap().code, 5);
    })
    .join()
    .unwrap();
    assert_eq!(sched_getscheduler(0).unwrap(), parent);
    assert_eq!(getpriority(PriorityKind::Process, 0).unwrap(), parent_nice);
}
