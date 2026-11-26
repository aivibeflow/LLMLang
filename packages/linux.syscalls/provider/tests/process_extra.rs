use linux_syscalls_provider::{
    getcpu, gettid, membarrier_query, personality_query, sched_get_priority_max,
    sched_get_priority_min, sched_rr_get_interval, sched_yield, SyscallError, EINVAL, ENOSYS,
};
use std::thread;

extern "C" {
    #[link_name = "sched_rr_get_interval"]
    fn libc_sched_rr_get_interval(pid: i32, interval: *mut [i64; 2]) -> i32;
    #[link_name = "personality"]
    fn libc_personality(persona: u64) -> i32;
    fn __errno_location() -> *mut i32;
}

#[test]
fn thread_id_distinguishes_neighbor_threads() {
    let current = gettid().unwrap();
    let other = thread::spawn(|| gettid().unwrap()).join().unwrap();
    assert!(current > 0 && other > 0);
    assert_ne!(current, other);
    assert_eq!(gettid().unwrap(), current);
}

#[test]
fn scheduler_queries_preserve_bounds_and_errno() {
    sched_yield().unwrap();
    for realtime_policy in [1, 2] {
        assert_eq!(sched_get_priority_min(realtime_policy).unwrap(), 1);
        assert_eq!(sched_get_priority_max(realtime_policy).unwrap(), 99);
    }
    for ordinary_policy in [0, 3, 5, 6] {
        assert_eq!(sched_get_priority_min(ordinary_policy).unwrap(), 0);
        assert_eq!(sched_get_priority_max(ordinary_policy).unwrap(), 0);
    }
    assert!(sched_get_priority_min(-42).unwrap_err().is_errno(EINVAL));
    assert!(sched_get_priority_max(-42).unwrap_err().is_errno(EINVAL));
}

#[test]
fn round_robin_interval_matches_libc_and_rejects_invalid_pid() {
    let mut native = [0_i64; 2];
    assert_eq!(unsafe { libc_sched_rr_get_interval(0, &mut native) }, 0);
    let interval = sched_rr_get_interval(0).unwrap();
    assert_eq!([interval.seconds(), interval.nanos()], native);
    assert!(matches!(
        sched_rr_get_interval(-1),
        Err(SyscallError::InvalidInput(_))
    ));
    assert!(sched_rr_get_interval(i32::MAX).unwrap_err().is_errno(3)); // ESRCH
}

#[test]
fn cpu_location_and_readonly_query_modes_preserve_kernel_results() {
    let location = getcpu().unwrap();
    assert_ne!(location.cpu, u32::MAX);
    assert_ne!(location.node, u32::MAX);

    let (reference, errno) = unsafe {
        *__errno_location() = 0;
        let result = libc_personality(u32::MAX as u64);
        (result, *__errno_location())
    };
    let personality = personality_query();
    if reference == -1 && errno != 0 {
        assert!(personality.unwrap_err().is_errno(errno));
    } else {
        assert_eq!(personality.unwrap(), reference as u32);
    }

    let commands = membarrier_query();
    match commands {
        Ok(mask) => assert_eq!(membarrier_query().unwrap(), mask),
        Err(error) => assert!(error.is_errno(ENOSYS) || error.is_errno(1)), // EPERM (host policy)
    }
}
