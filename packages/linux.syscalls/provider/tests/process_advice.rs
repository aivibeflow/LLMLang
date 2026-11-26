use linux_syscalls_provider::*;

#[test]
fn process_madvise_self_preserves_mapping_bytes_or_native_denial() {
    let mut mapping = mmap(4097, Protection::ReadWrite).unwrap();
    let bytes = mapping.as_mut_slice().unwrap();
    bytes[..4].copy_from_slice(b"head");
    bytes[4096] = b'z';
    mprotect(&mut mapping, Protection::ReadOnly).unwrap();
    for advice in [ProcessAdvice::WillNeed, ProcessAdvice::Cold] {
        match process_madvise(&mut mapping, advice) {
            Ok(progress) => assert_eq!(progress, 4097),
            Err(error) if [1, 13, 38].into_iter().any(|code| error.is_errno(code)) => {
                eprintln!("process_madvise host availability: {error:?}");
            }
            Err(error) => panic!("unexpected process_madvise errno: {error:?}"),
        }
        assert_eq!(&mapping.as_slice()[..4], b"head");
        assert_eq!(mapping.as_slice()[4096], b'z');
        assert!(mapping.as_mut_slice().is_none());
    }
    munmap(mapping).unwrap();
}

#[test]
fn process_mrelease_preserves_errors_for_running_and_reaped_own_child() {
    let image = ExecImage::new(c"/bin/sleep", &[c"sleep", c"1"], &[]).unwrap();
    let mut child = fork_execve(&image).unwrap();
    let target = pidfd_open(&child).unwrap();
    let running = process_mrelease(&target);
    pidfd_send_signal(&target, ChildSignal::Terminate).unwrap();
    loop {
        match wait4(&mut child, 0) {
            Ok(Some(status)) => {
                assert_eq!(status.signal(), Some(15));
                break;
            }
            Err(error) if error.is_errno(EINTR) => continue,
            result => panic!("unexpected wait status: {result:?}"),
        }
    }
    assert!(child.pid().is_none());

    for (result, state_error) in [(running, 22), (process_mrelease(&target), 3)] {
        let error = result.unwrap_err();
        assert!(
            [state_error, 1, 13, 38]
                .into_iter()
                .any(|code| error.is_errno(code)),
            "unexpected process_mrelease errno: {error:?}"
        );
        eprintln!("process_mrelease host status: {error:?}");
    }
}
