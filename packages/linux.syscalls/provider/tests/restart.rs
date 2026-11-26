use linux_syscalls_provider::{restart_syscall, EINTR};

#[test]
fn restart_syscall_preserves_inactive_thread_eintr() {
    let thread = std::thread::spawn(restart_syscall);
    assert!(thread.join().unwrap().unwrap_err().is_errno(EINTR));
}
