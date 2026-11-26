//! Run the privileged inode-notification fixture only in the disposable guest.
use linux_syscalls_provider::*;
use std::fs::{File, OpenOptions};
use std::io::Write;
use std::os::fd::AsFd;

const GUEST_ARGUMENT: &str = "--llmlang-disposable-guest-probe";

fn main() -> Result<(), Box<dyn std::error::Error>> {
    assert!(std::env::args().skip(1).eq([GUEST_ARGUMENT]));
    assert_eq!(getppid()?, 1, "run through the disposable guest init");

    let marked_path = "/llmlang-fanotify-marked";
    let other_path = "/llmlang-fanotify-unmarked";
    std::fs::write(marked_path, b"initial")?;
    std::fs::write(other_path, b"other")?;
    let marked = File::open(marked_path)?;
    let other = File::open(other_path)?;

    let mut group = fanotify_init()?;
    let mask = FanotifyMask::OPEN.combine(FanotifyMask::MODIFY);
    fanotify_mark(&mut group, marked.as_fd(), FanotifyMarkAction::Add, mask)?;
    assert!(matches!(
        fanotify_mark(&mut group, other.as_fd(), FanotifyMarkAction::Add, mask),
        Err(SyscallError::InvalidInput(_))
    ));
    assert!(matches!(
        fanotify_mark(
            &mut group,
            marked.as_fd(),
            FanotifyMarkAction::Remove,
            FanotifyMask::OPEN
        ),
        Err(SyscallError::InvalidInput(_))
    ));
    assert!(read_fanotify_event(&group).unwrap_err().is_errno(EAGAIN));
    drop(File::open(other_path)?);
    assert!(read_fanotify_event(&group).unwrap_err().is_errno(EAGAIN));

    let mut writer = OpenOptions::new().write(true).open(marked_path)?;
    writer.write_all(b"updated")?;
    drop(writer);
    let mut seen = 0;
    loop {
        let event = match read_fanotify_event(&group) {
            Ok(event) => event,
            Err(error) if error.is_errno(EAGAIN) => break,
            Err(error) => return Err(error.into()),
        };
        seen |= event.mask;
        assert_eq!(event.pid, getpid()?);
        let file = event
            .file
            .expect("inode notification should own a descriptor");
        assert_eq!(fcntl_getfd(file.borrow())? & 1, 1);
        assert_eq!(fcntl_getfl(file.borrow())? & 3, O_RDONLY);
        let mut data = [0; 7];
        assert_eq!(read(file.borrow(), &mut data)?, ReadOutcome::Progress(7));
        assert_eq!(&data, b"updated");
        close(file)?;
    }
    assert_eq!(seen, mask.bits());
    println!("LLMLANG_GUEST_CASE fanotify_selects_one_inode_and_delivers_owned_event_fds");

    fanotify_mark(&mut group, marked.as_fd(), FanotifyMarkAction::Remove, mask)?;
    drop(File::open(marked_path)?);
    assert!(read_fanotify_event(&group).unwrap_err().is_errno(EAGAIN));
    println!("LLMLANG_GUEST_CASE fanotify_removes_exact_mark_and_preserves_empty_queue_errno");

    drop(group);
    setuid(UserId::new(65_534)?)?;
    assert!(fanotify_init().unwrap_err().is_errno(1));
    println!("LLMLANG_GUEST_CASE fanotify_descriptor_mode_requires_privilege");
    Ok(())
}
