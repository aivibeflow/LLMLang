//! Positive software-clock and bounded io_uring observations in the guest.
use linux_syscalls_provider::*;
use std::hint::black_box;

fn main() -> Result<(), SyscallError> {
    let counter = perf_event_open_task_clock()?;
    let observe = || {
        let mut bytes = [0; 8];
        assert_eq!(
            read(counter.borrow(), &mut bytes).unwrap(),
            ReadOutcome::Progress(8)
        );
        u64::from_ne_bytes(bytes)
    };
    let start = observe();
    let mut work = 0_u64;
    for value in 0..100_000_u64 {
        work = work.wrapping_add(black_box(value));
    }
    black_box(work);
    assert!(observe() > start);
    close(counter)?;
    println!("LLMLANG_GUEST_CASE perf_task_clock_ticks");

    let (ring, info) = io_uring_setup(4)?;
    assert!(info.submission_entries >= 4);
    assert!(info.completion_entries >= info.submission_entries);
    println!("LLMLANG_GUEST_CASE io_uring_setup_returns_owned_ring");

    let probe = io_uring_register_probe(ring.borrow())?;
    assert!(probe
        .operations
        .iter()
        .any(|operation| operation.opcode == 0 && operation.flags & 1 == 1));
    close(ring)?;
    println!("LLMLANG_GUEST_CASE io_uring_probe_reports_nop");
    io_uring_nop()?;
    println!("LLMLANG_GUEST_CASE io_uring_nop_completes");
    Ok(())
}
