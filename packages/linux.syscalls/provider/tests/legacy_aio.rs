use linux_syscalls_provider::{
    io_cancel, io_destroy, io_getevents, io_pgetevents, io_setup, io_submit_fsync, AioFsyncEvent,
    LegacyAioContext, SyscallError, EINVAL,
};
use std::fs::{self, File, OpenOptions};
use std::io::Write;
use std::os::fd::AsFd;
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
use std::thread;
use std::time::{Duration, Instant};

struct TempFile(PathBuf);

impl TempFile {
    fn create() -> (Self, File) {
        static NEXT_FILE: AtomicU64 = AtomicU64::new(0);
        let path = std::env::temp_dir().join(format!(
            "llmlang-legacy-aio-{}-{}",
            std::process::id(),
            NEXT_FILE.fetch_add(1, Ordering::Relaxed)
        ));
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .create_new(true)
            .open(&path)
            .unwrap();
        (Self(path), file)
    }
}

impl Drop for TempFile {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.0);
    }
}

fn await_event(
    context: &mut LegacyAioContext,
    reap: fn(&mut LegacyAioContext) -> Result<Vec<AioFsyncEvent>, SyscallError>,
) -> AioFsyncEvent {
    let deadline = Instant::now() + Duration::from_secs(2);
    loop {
        let events = reap(context).unwrap();
        if !events.is_empty() {
            assert_eq!(events.len(), 1);
            return events[0];
        }
        assert!(
            Instant::now() < deadline,
            "AIO fsync completion did not arrive within 2 seconds"
        );
        thread::sleep(Duration::from_millis(1));
    }
}

#[test]
fn legacy_aio_context_validates_limits_and_destroyed_state() {
    for invalid in [0, 17, u32::MAX] {
        assert!(matches!(
            io_setup(invalid),
            Err(SyscallError::InvalidInput(_))
        ));
    }
    let mut context = io_setup(1).unwrap();
    assert_eq!(io_getevents(&mut context).unwrap(), []);
    assert_eq!(io_pgetevents(&mut context).unwrap(), []);
    io_destroy(&mut context).unwrap();
    assert!(matches!(
        io_destroy(&mut context),
        Err(SyscallError::InvalidInput(_))
    ));
    assert!(matches!(
        io_getevents(&mut context),
        Err(SyscallError::InvalidInput(_))
    ));
    assert!(matches!(
        io_pgetevents(&mut context),
        Err(SyscallError::InvalidInput(_))
    ));
}

#[test]
fn legacy_aio_fsync_has_stable_tags_and_kernel_file_reference() {
    let (path, mut file) = TempFile::create();
    let mut context = io_setup(1).unwrap();
    file.write_all(b"legacy AIO sync").unwrap();
    let first = io_submit_fsync(&mut context, file.as_fd()).unwrap();
    assert!(matches!(
        io_submit_fsync(&mut context, file.as_fd()),
        Err(SyscallError::InvalidInput(_))
    ));
    drop(file);
    let event = await_event(&mut context, io_getevents);
    assert_eq!(event.request, first);
    assert_eq!(event.outcome, Ok(()));
    assert_eq!(fs::read(&path.0).unwrap(), b"legacy AIO sync");

    let file = File::open(&path.0).unwrap();
    let second = io_submit_fsync(&mut context, file.as_fd()).unwrap();
    assert_ne!(second, first);
    let event = await_event(&mut context, io_pgetevents);
    assert_eq!(event.request, second);
    assert_eq!(event.outcome, Ok(()));
    io_destroy(&mut context).unwrap();
}

#[test]
fn legacy_aio_reports_kernel_error_and_destroy_drains_pending_fsync() {
    let mut context = io_setup(1).unwrap();
    let unsupported = File::open("/dev/null").unwrap();
    assert!(io_submit_fsync(&mut context, unsupported.as_fd())
        .unwrap_err()
        .is_errno(EINVAL));
    assert_eq!(io_getevents(&mut context).unwrap(), []);

    let (path, mut file) = TempFile::create();
    file.write_all(b"destroy drains pending sync").unwrap();
    io_submit_fsync(&mut context, file.as_fd()).unwrap();
    drop(file);
    io_destroy(&mut context).unwrap();
    assert_eq!(fs::read(&path.0).unwrap(), b"destroy drains pending sync");
}

#[test]
fn legacy_aio_cancel_rejects_foreign_and_reaped_tags_and_preserves_fsync_completion() {
    let (_path, mut file) = TempFile::create();
    file.write_all(b"retain uncancellable fsync completions")
        .unwrap();
    let mut first = io_setup(1).unwrap();
    let mut second = io_setup(1).unwrap();
    let first_request = io_submit_fsync(&mut first, file.as_fd()).unwrap();
    let second_request = io_submit_fsync(&mut second, file.as_fd()).unwrap();
    assert_ne!(first_request, second_request);
    assert!(matches!(
        io_cancel(&mut first, second_request),
        Err(SyscallError::InvalidInput(_))
    ));
    assert!(io_cancel(&mut first, first_request)
        .unwrap_err()
        .is_errno(EINVAL));
    assert!(matches!(
        io_submit_fsync(&mut first, file.as_fd()),
        Err(SyscallError::InvalidInput(_))
    ));

    let first_event = await_event(&mut first, io_getevents);
    assert_eq!(first_event.request, first_request);
    assert_eq!(first_event.outcome, Ok(()));
    assert!(matches!(
        io_cancel(&mut first, first_request),
        Err(SyscallError::InvalidInput(_))
    ));
    let second_event = await_event(&mut second, io_pgetevents);
    assert_eq!(second_event.request, second_request);
    assert_eq!(second_event.outcome, Ok(()));
    io_destroy(&mut first).unwrap();
    io_destroy(&mut second).unwrap();
}

#[test]
fn legacy_aio_cancel_acknowledges_queued_empty_pipe_poll_and_reaps_matching_completion() {
    use linux_syscalls_provider::{
        io_getevents_cancelled_pipe_poll, io_submit_cancellable_pipe_poll, AioCancelStatus,
    };

    let mut context = io_setup(1).unwrap();
    let request = io_submit_cancellable_pipe_poll(&mut context).unwrap();
    assert_eq!(io_getevents_cancelled_pipe_poll(&mut context).unwrap(), []);
    assert!(matches!(
        io_getevents(&mut context),
        Err(SyscallError::InvalidInput(_))
    ));
    assert_eq!(
        io_cancel(&mut context, request).unwrap(),
        AioCancelStatus::CompletionPending
    );
    assert!(io_cancel(&mut context, request)
        .unwrap_err()
        .is_errno(EINVAL));

    let deadline = Instant::now() + Duration::from_secs(2);
    loop {
        let completions = io_getevents_cancelled_pipe_poll(&mut context).unwrap();
        if let [completion] = completions.as_slice() {
            assert_eq!(completion.request, request);
            assert_eq!(completion.outcome, Ok(()));
            break;
        }
        assert!(completions.is_empty());
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
    assert_eq!(io_getevents(&mut context).unwrap(), []);
    let pending_at_destroy = io_submit_cancellable_pipe_poll(&mut context).unwrap();
    assert_ne!(pending_at_destroy, request);
    io_destroy(&mut context).unwrap();
    assert!(matches!(
        io_cancel(&mut context, pending_at_destroy),
        Err(SyscallError::InvalidInput(_))
    ));
}
