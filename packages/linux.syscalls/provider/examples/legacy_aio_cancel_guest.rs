//! Verify the pinned Linux AIO poll cancellation path on an owned empty pipe.
use linux_syscalls_provider::{
    getppid, io_cancel, io_destroy, io_getevents_cancelled_pipe_poll, io_setup,
    io_submit_cancellable_pipe_poll, AioCancelStatus, SyscallError, EINVAL,
};
use std::thread;
use std::time::{Duration, Instant};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    assert!(std::env::args()
        .skip(1)
        .eq(["--llmlang-disposable-guest-probe"]));
    assert_eq!(getppid()?, 1, "run through the disposable guest init");

    let mut context = io_setup(1)?;
    let request = io_submit_cancellable_pipe_poll(&mut context)?;
    assert!(io_getevents_cancelled_pipe_poll(&mut context)?.is_empty());
    assert_eq!(
        io_cancel(&mut context, request)?,
        AioCancelStatus::CompletionPending
    );
    assert!(io_cancel(&mut context, request)
        .unwrap_err()
        .is_errno(EINVAL));

    let deadline = Instant::now() + Duration::from_secs(2);
    loop {
        let events = io_getevents_cancelled_pipe_poll(&mut context)?;
        if let [event] = events.as_slice() {
            assert_eq!(event.request, request);
            assert_eq!(event.outcome, Ok(()));
            break;
        }
        assert!(events.is_empty());
        assert!(
            Instant::now() < deadline,
            "cancelled poll completion timed out"
        );
        thread::sleep(Duration::from_millis(1));
    }
    assert!(matches!(
        io_cancel(&mut context, request),
        Err(SyscallError::InvalidInput(_))
    ));
    io_destroy(&mut context)?;
    println!("LLMLANG_GUEST_CASE legacy_aio_cancel_acknowledges_queued_empty_pipe_poll_and_reaps_matching_completion");
    Ok(())
}
