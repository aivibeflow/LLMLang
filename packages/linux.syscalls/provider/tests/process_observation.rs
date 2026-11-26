use linux_syscalls_provider::*;
use std::ffi::CString;
use std::os::fd::AsRawFd;

#[test]
fn waitid_observes_nonblocking_absence_and_consumes_one_exit() {
    let (reader, writer) = pipe().unwrap();
    let command = CString::new(format!(
        "read value </proc/self/fd/{}; exit 41",
        reader.as_raw_fd()
    ))
    .unwrap();
    let image = ExecImage::new(c"/bin/sh", &[c"sh", c"-c", &command], &[]).unwrap();
    let mut child = fork_execve(&image).unwrap();
    let pid = child.pid().unwrap();
    assert_eq!(waitid(&mut child, true).unwrap(), None);
    assert_eq!(child.pid(), Some(pid));
    assert_eq!(write(writer.borrow(), b"go\n").unwrap(), 3);
    let result = waitid(&mut child, false).unwrap().unwrap();
    assert_eq!(result.pid, pid);
    assert_eq!(result.outcome, WaitIdOutcome::Exited(41));
    assert!(child.pid().is_none());
    assert!(matches!(
        waitid(&mut child, false),
        Err(SyscallError::InvalidInput(_))
    ));
}

#[test]
fn waitid_preserves_signal_outcomes() {
    let (reader, _writer) = pipe().unwrap();
    let command = CString::new(format!(
        "read value </proc/self/fd/{}; exit 0",
        reader.as_raw_fd()
    ))
    .unwrap();
    let image = ExecImage::new(c"/bin/sh", &[c"sh", c"-c", &command], &[]).unwrap();
    let mut child = fork_execve(&image).unwrap();
    let pidfd = pidfd_open(&child).unwrap();
    pidfd_send_signal(&pidfd, ChildSignal::Terminate).unwrap();
    assert_eq!(
        waitid(&mut child, false).unwrap().unwrap().outcome,
        WaitIdOutcome::Signaled {
            signal: 15,
            core_dumped: false
        }
    );
}

#[test]
fn brk_zero_observes_without_requesting_a_heap_change() {
    let before = brk_query().unwrap();
    let after = brk_query().unwrap();
    assert_eq!(before, after);
    assert!(before > 0);
}
