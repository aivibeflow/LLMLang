use linux_syscalls_provider::{
    getgroups, getresgid, getresuid, setfsgid_query, setfsuid_query, setgid, setgroups, setregid,
    setresgid, setresuid, setreuid, setuid, GroupId, SyscallError, UserId,
};
use std::{env, process::Command};

const CHILD: &str = "LLMLANG_SYSCALL_CREDENTIAL_TEST_CHILD";
const CASE: &str = "settled_current_ids_are_preserved_in_a_disposable_host_child";

fn supplementary_groups() -> Vec<u32> {
    let count = getgroups(&mut []).unwrap();
    let mut groups = vec![0; count];
    assert_eq!(getgroups(&mut groups).unwrap(), groups.len());
    groups
}

#[test]
fn invalid_credential_selectors_are_rejected() {
    assert!(matches!(
        UserId::new(u32::MAX),
        Err(SyscallError::InvalidInput(_))
    ));
    assert!(matches!(
        GroupId::new(u32::MAX),
        Err(SyscallError::InvalidInput(_))
    ));
    let oversized = vec![GroupId::new(0).unwrap(); 65_537];
    assert!(matches!(
        setgroups(&oversized),
        Err(SyscallError::InvalidInput(_))
    ));
}

#[test]
fn settled_current_ids_are_preserved_in_a_disposable_host_child() {
    let users = getresuid().unwrap();
    let groups = getresgid().unwrap();
    let supplementary = supplementary_groups();
    if env::var_os(CHILD).is_some() {
        // Run native setters only when the child starts with ordinary, equal
        // real/effective/saved/filesystem IDs, so requests are no-ops by value.
        if users.real != users.effective
            || users.real != users.saved
            || users.real != setfsuid_query().unwrap()
            || groups.real != groups.effective
            || groups.real != groups.saved
            || groups.real != setfsgid_query().unwrap()
        {
            panic!("host credential case requires ordinary, settled caller IDs");
        }
        let user = UserId::new(users.real).unwrap();
        let group = GroupId::new(groups.real).unwrap();
        setuid(user).unwrap();
        setgid(group).unwrap();
        setreuid(None, Some(user)).unwrap();
        setregid(None, Some(group)).unwrap();
        setresuid(Some(user), None, None).unwrap();
        setresgid(Some(group), None, None).unwrap();
        let supplied: Vec<_> = supplementary
            .iter()
            .map(|id| GroupId::new(*id).unwrap())
            .collect();
        if let Err(error) = setgroups(&supplied) {
            assert!(error.is_errno(1)); // EPERM without CAP_SETGID
        }
    } else {
        let child = Command::new(env::current_exe().unwrap())
            .args(["--exact", CASE, "--nocapture"])
            .env(CHILD, "1")
            .output()
            .unwrap();
        assert!(
            child.status.success(),
            "{}{}",
            String::from_utf8_lossy(&child.stdout),
            String::from_utf8_lossy(&child.stderr)
        );
    }
    assert_eq!(getresuid().unwrap(), users);
    assert_eq!(getresgid().unwrap(), groups);
    assert_eq!(supplementary_groups(), supplementary);
}
