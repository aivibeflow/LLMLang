use linux_syscalls_provider::*;
use std::env;
use std::ffi::CString;
use std::fs::{self, File};
use std::io::Read;
use std::os::fd::AsFd;
use std::os::raw::{c_int, c_ulong};

const PR_SET_NO_NEW_PRIVS: c_int = 38;
const FD_CLOEXEC: i32 = 1;
const EACCES: i32 = 13;
const EBADFD: i32 = 77;
const O_PATH: i32 = 0o10000000;

extern "C" {
    fn prctl(option: c_int, ...) -> c_int;
}

fn case(name: &str) {
    println!("LLMLANG_GUEST_CASE {name}");
}

fn path_fd(path: &str) -> Result<LinuxFd, SyscallError> {
    let path = CString::new(path).expect("static path contains no NUL");
    openat(
        Directory::Current,
        &path,
        OpenOptions {
            flags: O_PATH | O_DIRECTORY,
            mode: 0,
        },
    )
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    assert_eq!(
        env::args().nth(1).as_deref(),
        Some("--llmlang-disposable-guest-probe")
    );
    assert_eq!(getppid()?, 1, "run through the disposable guest init");

    let version = landlock_create_ruleset_version()?;
    println!("Landlock kernel ABI {version}");
    assert!(version >= 1);
    let mut ruleset = landlock_create_ruleset()?;
    assert_eq!(fcntl_getfd(ruleset.as_fd())? & FD_CLOEXEC, FD_CLOEXEC);
    case("landlock_version_and_ruleset_cloexec");

    let (pipe_reader, pipe_writer) = pipe2(0)?;
    let invalid_parent = landlock_add_rule(
        &mut ruleset,
        pipe_reader.borrow(),
        LandlockReadAccess::Files,
    )
    .unwrap_err();
    assert!(invalid_parent.is_errno(EBADFD), "{invalid_parent}");
    close(pipe_reader)?;
    close(pipe_writer)?;
    case("landlock_rejects_nonfilesystem_parent");

    for path in ["/llmlang-allowed", "/llmlang-denied", "/llmlang-list-only"] {
        fs::create_dir(path)?;
    }
    let allowed = "/llmlang-allowed/input";
    let denied = "/llmlang-denied/input";
    let list_only = "/llmlang-list-only/input";
    fs::write(allowed, b"allowed")?;
    fs::write(denied, b"denied")?;
    fs::write(list_only, b"listed")?;
    let mut retained = File::open(denied)?;
    let allowed_parent = path_fd("/llmlang-allowed")?;
    let denied_parent = path_fd("/llmlang-denied")?;
    let listing_parent = path_fd("/llmlang-list-only")?;

    landlock_add_rule(
        &mut ruleset,
        allowed_parent.borrow(),
        LandlockReadAccess::FilesAndDirectories,
    )?;
    landlock_add_rule(
        &mut ruleset,
        listing_parent.borrow(),
        LandlockReadAccess::Directories,
    )?;

    // This irreversible step applies to the test process in the guest only.
    assert_eq!(
        unsafe {
            prctl(
                PR_SET_NO_NEW_PRIVS,
                1 as c_ulong,
                0 as c_ulong,
                0 as c_ulong,
                0 as c_ulong,
            )
        },
        0
    );
    assert!(prctl_get_no_new_privs()?);
    landlock_restrict_self(&ruleset)?;

    assert_eq!(fs::read(allowed)?, b"allowed");
    assert_eq!(fs::read(denied).unwrap_err().raw_os_error(), Some(EACCES));
    assert_eq!(
        fs::read(list_only).unwrap_err().raw_os_error(),
        Some(EACCES)
    );
    assert_eq!(fs::read_dir("/llmlang-list-only")?.count(), 1);
    assert_eq!(
        fs::read_dir("/llmlang-denied").unwrap_err().raw_os_error(),
        Some(EACCES)
    );
    case("landlock_read_policy_enters_allowlist_and_denies_unlisted");

    let mut old_content = Vec::new();
    retained.read_to_end(&mut old_content)?;
    assert_eq!(old_content, b"denied");
    case("landlock_existing_open_descriptor_remains_readable");

    landlock_add_rule(
        &mut ruleset,
        denied_parent.borrow(),
        LandlockReadAccess::FilesAndDirectories,
    )?;
    landlock_restrict_self(&ruleset)?;
    close(ruleset.into_fd())?;
    assert_eq!(fs::read(allowed)?, b"allowed");
    assert_eq!(fs::read(denied).unwrap_err().raw_os_error(), Some(EACCES));
    case("landlock_later_layer_cannot_relax_restriction");

    close(allowed_parent)?;
    close(denied_parent)?;
    close(listing_parent)?;
    Ok(())
}
