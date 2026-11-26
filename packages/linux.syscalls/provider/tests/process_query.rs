use linux_syscalls_provider::{
    getpgid, getpid, getpriority, getrlimit, getrusage, getsid, prlimit64, sched_getparam,
    sched_getscheduler, Limit, LimitResource, PriorityKind, SyscallError, UsageScope,
};

extern "C" {
    #[link_name = "getpriority"]
    fn libc_getpriority(which: i32, who: u32) -> i32;
    #[link_name = "getrusage"]
    fn libc_getrusage(who: i32, usage: *mut [i64; 18]) -> i32;
    fn __errno_location() -> *mut i32;
}

#[test]
fn resource_limit_queries_agree_for_current_process() {
    let selectors = [
        LimitResource::Cpu,
        LimitResource::FileSize,
        LimitResource::Data,
        LimitResource::Stack,
        LimitResource::Core,
        LimitResource::ResidentSet,
        LimitResource::Processes,
        LimitResource::OpenFiles,
        LimitResource::LockedMemory,
        LimitResource::AddressSpace,
        LimitResource::Locks,
        LimitResource::PendingSignals,
        LimitResource::MessageQueue,
        LimitResource::Nice,
        LimitResource::RealtimePriority,
        LimitResource::RealtimeTime,
    ];
    for selector in selectors {
        let first = getrlimit(selector).unwrap();
        assert_eq!(first, prlimit64(selector).unwrap(), "{selector:?}");
        match (first.soft, first.hard) {
            (Limit::Finite(soft), Limit::Finite(hard)) => assert!(soft <= hard, "{selector:?}"),
            (Limit::Unlimited, Limit::Finite(_)) => panic!("inconsistent limit for {selector:?}"),
            (_, Limit::Unlimited) => {}
        }
    }
}

#[test]
fn process_group_session_and_scheduler_accept_current_pid() {
    let pid = getpid().unwrap();
    assert_eq!(getpgid(0).unwrap(), getpgid(pid).unwrap());
    assert_eq!(getsid(0).unwrap(), getsid(pid).unwrap());

    // Zero selects the calling thread. The explicit process ID can select a
    // different thread of the test binary and need only return a valid result.
    for selected in [0, pid] {
        assert!(sched_getscheduler(selected).unwrap().code >= 0);
        assert!((0..=99).contains(&sched_getparam(selected).unwrap()));
    }
}

#[test]
fn process_queries_reject_negative_and_nonexistent_pid() {
    let queries: [fn(i32) -> Result<i32, SyscallError>; 4] =
        [getpgid, getsid, sched_getparam, |pid| {
            sched_getscheduler(pid).map(|policy| policy.code)
        }];
    for query in queries {
        assert!(matches!(query(-1), Err(SyscallError::InvalidInput(_))));
        assert!(query(i32::MAX).unwrap_err().is_errno(3)); // ESRCH
    }
}

#[test]
fn priority_query_preserves_nice_and_errno_envelopes() {
    let libc_nice = unsafe {
        *__errno_location() = 0;
        let nice = libc_getpriority(0, 0);
        assert_eq!(*__errno_location(), 0);
        nice
    };
    assert_eq!(getpriority(PriorityKind::Process, 0).unwrap(), libc_nice);
    for kind in [PriorityKind::ProcessGroup, PriorityKind::User] {
        assert!((-20..=19).contains(&getpriority(kind, 0).unwrap()));
    }
    assert!(getpriority(PriorityKind::Process, i32::MAX as u32)
        .unwrap_err()
        .is_errno(3)); // ESRCH
}

fn libc_usage() -> [i64; 18] {
    let mut bytes = [0_i64; 18];
    assert_eq!(unsafe { libc_getrusage(0, &mut bytes) }, 0);
    bytes
}

#[test]
fn resource_usage_matches_native_layout_and_time_ranges() {
    let reference_before = libc_usage();
    let process = getrusage(UsageScope::Process).unwrap();
    let reference_after = libc_usage();
    for (index, value) in [
        (4, process.max_rss_kib),
        (8, process.minor_faults),
        (9, process.major_faults),
        (16, process.voluntary_context_switches),
        (17, process.involuntary_context_switches),
    ] {
        assert!((reference_before[index]..=reference_after[index]).contains(&value));
    }

    for scope in [
        UsageScope::CallingThread,
        UsageScope::Children,
        UsageScope::Process,
    ] {
        let usage = getrusage(scope).unwrap();
        assert!(usage.user.microseconds < 1_000_000);
        assert!(usage.system.microseconds < 1_000_000);
    }
}
