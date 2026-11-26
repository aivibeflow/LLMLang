use linux_syscalls_provider::*;
use std::ffi::CString;
use std::os::fd::AsRawFd;

fn availability_error(error: SyscallError) -> bool {
    error.is_errno(1) || error.is_errno(13) || error.is_errno(ENOSYS)
}

#[test]
fn kcmp_self_compares_borrowed_open_file_descriptions() {
    let (reader, writer) = pipe().unwrap();
    let duplicate = dup(reader.borrow()).unwrap();
    if let Err(error) = kcmp(reader.borrow(), duplicate.borrow()) {
        assert!(availability_error(error), "unexpected kcmp errno {error:?}");
        eprintln!("kcmp host availability: {error:?}");
        return;
    }
    assert!(kcmp(reader.borrow(), duplicate.borrow()).unwrap());
    assert!(kcmp(reader.borrow(), reader.borrow()).unwrap());
    assert!(!kcmp(reader.borrow(), writer.borrow()).unwrap());
}

#[test]
fn pidfd_getfd_checks_the_recorded_description_or_preserves_denial() {
    let (expected, _expected_writer) = pipe().unwrap();
    let (hold, release) = pipe().unwrap();
    let command = CString::new(format!(
        "IFS= read -r token < /proc/self/fd/{}; exit 45",
        hold.as_raw_fd()
    ))
    .unwrap();
    let image = ExecImage::new(c"/bin/sh", &[c"sh", c"-c", &command], &[]).unwrap();
    let mut child = fork_execve(&image).unwrap();
    let target = pidfd_open(&child).unwrap();
    let known = KnownChildDescriptor::new(&target, expected.borrow());
    let result = pidfd_getfd(&known);

    let released = write(release.borrow(), b"release\n");
    let status = loop {
        match wait4(&mut child, 0) {
            Err(error) if error.is_errno(EINTR) => continue,
            result => break result.unwrap().unwrap(),
        }
    };
    assert_eq!(released.unwrap(), 8);
    assert_eq!(status.exited(), Some(45));
    match result {
        Ok(duplicate) => {
            assert_eq!(fcntl_getfd(duplicate.borrow()).unwrap() & 1, 1);
            assert!(kcmp(expected.borrow(), duplicate.borrow()).unwrap());
            assert!(matches!(
                pidfd_getfd(&known),
                Err(ChildDescriptorError::Duplicate(error)) if error.is_errno(3)
            ));
        }
        Err(ChildDescriptorError::Duplicate(error) | ChildDescriptorError::Compare(error))
            if availability_error(error) =>
        {
            eprintln!("pidfd_getfd host availability: {error:?}");
        }
        Err(error) => panic!("unexpected descriptor result: {error:?}"),
    }
}
