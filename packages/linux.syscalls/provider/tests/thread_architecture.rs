use linux_syscalls_provider::{arch_prctl_get_fs, arch_prctl_get_gs};

unsafe extern "C" {
    fn syscall(number: std::ffi::c_long, ...) -> std::ffi::c_long;
}

#[test]
fn arch_prctl_observes_calling_thread_bases() {
    fn expected(selector: std::ffi::c_int) -> u64 {
        let mut output = 0_u64;
        assert_eq!(
            unsafe { syscall(158, selector, &mut output as *mut u64) },
            0
        );
        output
    }

    let fs = arch_prctl_get_fs().unwrap();
    assert_ne!(fs, 0);
    assert_eq!(fs, expected(0x1003));
    assert_eq!(arch_prctl_get_gs().unwrap(), expected(0x1004));

    let worker_fs = std::thread::spawn(|| {
        let observed = arch_prctl_get_fs().unwrap();
        assert_eq!(observed, expected(0x1003));
        assert_eq!(arch_prctl_get_gs().unwrap(), expected(0x1004));
        observed
    })
    .join()
    .unwrap();
    assert_ne!(worker_fs, fs);
    assert_eq!(arch_prctl_get_fs().unwrap(), fs);
}
