use linux_syscalls_provider::{
    close, fcntl_getfd, fcntl_getfl, ioctl_fionread, pipe2, prctl_get_name, prctl_get_no_new_privs,
    prctl_set_name, write, SyscallError, O_NONBLOCK,
};
use std::os::fd::AsFd;

#[test]
fn command_fcntl_getters_observe_pipe_flags() {
    let (reader, writer) = pipe2(O_NONBLOCK).unwrap();
    assert_eq!(fcntl_getfd(reader.borrow()).unwrap() & 1, 1);
    assert_eq!(
        fcntl_getfl(reader.borrow()).unwrap() & O_NONBLOCK,
        O_NONBLOCK
    );
    close(reader).unwrap();
    close(writer).unwrap();
}

#[test]
fn command_fionread_observes_pipe_bytes_without_consuming() {
    let unsupported = std::fs::File::open("/dev/null").unwrap();
    assert!(ioctl_fionread(unsupported.as_fd())
        .unwrap_err()
        .is_errno(25));

    let (reader, writer) = pipe2(0).unwrap();
    assert_eq!(ioctl_fionread(reader.borrow()).unwrap(), 0);
    assert_eq!(write(writer.borrow(), b"hello").unwrap(), 5);
    assert_eq!(ioctl_fionread(reader.borrow()).unwrap(), 5);
    assert_eq!(ioctl_fionread(reader.borrow()).unwrap(), 5);
    close(reader).unwrap();
    close(writer).unwrap();
}

#[test]
fn command_prctl_observes_no_new_privs() {
    let status = std::fs::read_to_string("/proc/thread-self/status").unwrap();
    let observed = status
        .lines()
        .find_map(|line| line.strip_prefix("NoNewPrivs:"))
        .unwrap();
    assert_eq!(prctl_get_no_new_privs().unwrap(), observed.trim() == "1");
}

#[test]
fn current_thread_name_round_trips_and_rejects_overlength() {
    let original = prctl_get_name().unwrap();
    std::thread::Builder::new()
        .name("test-original".into())
        .spawn(|| {
            assert_eq!(prctl_get_name().unwrap().as_c_str(), c"test-original");
            prctl_set_name(c"123456789abcdef").unwrap();
            assert_eq!(prctl_get_name().unwrap().as_c_str(), c"123456789abcdef");
            assert!(matches!(
                prctl_set_name(c"123456789abcdefg"),
                Err(SyscallError::InvalidInput(_))
            ));
            assert_eq!(prctl_get_name().unwrap().as_c_str(), c"123456789abcdef");
            prctl_set_name(c"").unwrap();
            assert_eq!(prctl_get_name().unwrap().as_c_str(), c"");
        })
        .unwrap()
        .join()
        .unwrap();
    assert_eq!(prctl_get_name().unwrap(), original);
}
