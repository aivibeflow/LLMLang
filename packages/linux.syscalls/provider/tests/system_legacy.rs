use linux_syscalls_provider::*;

#[test]
fn legacy_system_queries_preserve_kernel_availability() {
    for call in [
        syslog_buffer_size as fn() -> Result<usize, SyscallError>,
        sysfs_count,
    ] {
        match call() {
            Ok(count) => assert!(count > 0),
            Err(error) if error.is_errno(1) || error.is_errno(13) || error.is_errno(ENOSYS) => (),
            Err(error) => panic!("unexpected legacy system query: {error}"),
        }
    }
}
