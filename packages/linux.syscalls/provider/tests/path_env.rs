use linux_syscalls_provider::*;
use std::ffi::CString;
use std::fs::File;
use std::os::fd::AsFd;
use std::os::unix::ffi::OsStrExt;
use std::os::unix::fs::PermissionsExt;
use std::path::PathBuf;
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

#[test]
fn directory_context_and_umask_change_only_inside_child() {
    const CHILD: &str = "LLMLANG_PATH_ENV_CHILD";
    if std::env::var_os(CHILD).is_none() {
        let status = Command::new(std::env::current_exe().unwrap())
            .args([
                "--exact",
                "directory_context_and_umask_change_only_inside_child",
                "--nocapture",
            ])
            .env(CHILD, "1")
            .status()
            .unwrap();
        assert!(status.success());
        return;
    }

    struct Scratch(PathBuf);
    impl Drop for Scratch {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.0);
        }
    }

    let original = File::open(".").unwrap();
    let original_path = std::env::current_dir().unwrap();
    let stamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let scratch =
        Scratch(std::env::temp_dir().join(format!("llmlang-cwd-{}-{stamp}", std::process::id())));
    std::fs::create_dir(&scratch.0).unwrap();
    let absolute = std::fs::canonicalize(&scratch.0).unwrap();
    let target = CString::new(absolute.as_os_str().as_bytes()).unwrap();
    let directory = File::open(&absolute).unwrap();

    assert!(getcwd(&mut [0; 1]).unwrap_err().is_errno(34));
    chdir(&target).unwrap();
    let mut buffer = [0xff; 4096];
    assert_eq!(getcwd(&mut buffer).unwrap(), target.as_c_str());
    assert_eq!(buffer[target.as_bytes_with_nul().len()], 0xff);
    assert!(chdir(c"missing-dir").unwrap_err().is_errno(2));

    let previous = umask(0o077).unwrap();
    assert!(matches!(umask(0o1000), Err(SyscallError::InvalidInput(_))));
    let file = File::create("secret").unwrap();
    assert_eq!(file.metadata().unwrap().permissions().mode() & 0o777, 0o600);
    assert!(fchdir(file.as_fd()).unwrap_err().is_errno(20));
    assert_eq!(umask(previous).unwrap(), 0o077);

    fchdir(original.as_fd()).unwrap();
    assert_eq!(std::env::current_dir().unwrap(), original_path);
    fchdir(directory.as_fd()).unwrap();
    assert_eq!(getcwd(&mut buffer).unwrap(), target.as_c_str());
    fchdir(original.as_fd()).unwrap();
}

#[test]
fn supplementary_groups_match_libc_and_preserve_unused_capacity() {
    extern "C" {
        #[link_name = "getgroups"]
        fn libc_getgroups(size: i32, groups: *mut u32) -> i32;
    }
    let count = getgroups(&mut []).unwrap();
    let mut expected = vec![0; count];
    assert_eq!(
        unsafe { libc_getgroups(count as i32, expected.as_mut_ptr()) },
        count as i32
    );
    let mut groups = vec![u32::MAX; count + 1];
    assert_eq!(getgroups(&mut groups).unwrap(), count);
    assert_eq!(groups[..count], expected);
    assert_eq!(groups[count], u32::MAX);
    if count > 1 {
        assert!(getgroups(&mut [0]).unwrap_err().is_errno(EINVAL));
    }
}
