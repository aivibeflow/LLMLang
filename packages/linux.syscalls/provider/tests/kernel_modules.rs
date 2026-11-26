use linux_syscalls_provider::*;

#[test]
fn kernel_modules_reject_empty_image_and_invalid_names_locally() {
    assert!(matches!(
        init_module(&[]),
        Err(SyscallError::InvalidInput(_))
    ));
    let long = std::ffi::CString::new(vec![b'A'; 56]).unwrap();
    for name in [c"", c"bad/name", c"bad name", c"\xFF", long.as_c_str()] {
        assert!(matches!(
            delete_module(name),
            Err(SyscallError::InvalidInput(_))
        ));
    }
}

#[test]
fn finit_module_rejects_writable_and_nonregular_descriptors_locally() {
    let writable = memfd_create(c"module-test").unwrap();
    let (reader, _writer) = pipe().unwrap();
    for descriptor in [&writable, &reader] {
        assert!(matches!(
            finit_module(descriptor.borrow()),
            Err(SyscallError::InvalidInput(_))
        ));
    }
}
