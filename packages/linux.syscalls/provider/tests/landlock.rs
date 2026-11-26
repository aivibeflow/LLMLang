use linux_syscalls_provider::*;
use std::os::fd::AsFd;

const EOPNOTSUPP: i32 = 95;
const FD_CLOEXEC: i32 = 1;

#[test]
fn landlock_native_query_or_explicit_unavailability() {
    match landlock_create_ruleset_version() {
        Ok(version) => {
            assert!(version >= 1);
            let ruleset = landlock_create_ruleset().unwrap();
            assert_eq!(
                fcntl_getfd(ruleset.as_fd()).unwrap() & FD_CLOEXEC,
                FD_CLOEXEC
            );
            close(ruleset.into_fd()).unwrap();
        }
        Err(error) => {
            assert!(
                error.is_errno(ENOSYS) || error.is_errno(EOPNOTSUPP),
                "{error}"
            );
            let creation = landlock_create_ruleset().unwrap_err();
            assert_eq!(creation, error);
            eprintln!("Landlock unavailable in the host profile: {error}");
        }
    }
}
