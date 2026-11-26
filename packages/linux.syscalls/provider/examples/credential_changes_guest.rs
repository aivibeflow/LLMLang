//! Observe native setters with isolated guest credentials and kernel state.
use linux_syscalls_provider::{
    capget, capset_clear, getgroups, getppid, getresgid, getresuid, prctl_get_no_new_privs,
    prctl_set_no_new_privs, setfsgid_query, setfsuid_query, setgid, setgroups, setregid, setresgid,
    setresuid, setreuid, setuid, CredentialIds, GroupId, UserId,
};
use std::{env, sync::mpsc, thread};

const GUEST_ARGUMENT: &str = "--llmlang-disposable-guest-probe";
const EPERM: i32 = 1;

fn case(name: &str) {
    println!("LLMLANG_GUEST_CASE {name}");
}

fn ids(real: u32, effective: u32, saved: u32) -> CredentialIds {
    CredentialIds {
        real,
        effective,
        saved,
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    assert!(env::args().skip(1).eq([GUEST_ARGUMENT]));
    assert_eq!(getppid()?, 1, "run through the disposable guest init");
    assert_eq!(getresuid()?, ids(0, 0, 0));
    assert_eq!(getresgid()?, ids(0, 0, 0));

    let initial_caps = capget()?;
    assert_ne!(initial_caps.effective, 0);
    let initial_nnp = prctl_get_no_new_privs()?;
    assert!(!initial_nnp);
    thread::spawn(|| {
        capset_clear().unwrap();
        let cleared = capget().unwrap();
        assert_eq!(
            [cleared.effective, cleared.permitted, cleared.inheritable],
            [0; 3]
        );
        prctl_set_no_new_privs().unwrap();
        assert!(prctl_get_no_new_privs().unwrap());
        prctl_set_no_new_privs().unwrap();
        assert!(prctl_get_no_new_privs().unwrap());
    })
    .join()
    .unwrap();
    assert_eq!(capget()?, initial_caps);
    assert_eq!(prctl_get_no_new_privs()?, initial_nnp);
    case("capability_clear_does_not_change_sibling");
    case("no_new_privs_is_monotone_and_thread_local");

    let mut supplementary = [u32::MAX; 2];
    setgroups(&[])?;
    assert_eq!(getgroups(&mut [])?, 0);
    setgroups(&[GroupId::new(3102)?, GroupId::new(3101)?])?;
    assert_eq!(getgroups(&mut supplementary)?, 2);
    assert_eq!(supplementary, [3101, 3102]);
    case("credential_setgroups_exact_and_empty");

    setregid(Some(GroupId::new(3001)?), None)?;
    assert_eq!(getresgid()?, ids(3001, 0, 0));
    assert_eq!(setfsgid_query()?, 0);
    case("credential_setregid_keeps_effective");
    setresgid(None, Some(GroupId::new(3002)?), Some(GroupId::new(3003)?))?;
    assert_eq!(getresgid()?, ids(3001, 3002, 3003));
    assert_eq!(setfsgid_query()?, 3002);
    case("credential_setresgid_updates_filesystem_id");
    setgid(GroupId::new(3004)?)?;
    assert_eq!(getresgid()?, ids(3004, 3004, 3004));
    assert_eq!(setfsgid_query()?, 3004);
    case("credential_setgid_privileged_updates_triplet");

    setreuid(Some(UserId::new(4001)?), None)?;
    assert_eq!(getresuid()?, ids(4001, 0, 0));
    assert_eq!(setfsuid_query()?, 0);
    case("credential_setreuid_keeps_effective");
    setresuid(None, None, Some(UserId::new(4002)?))?;
    let old = ids(4001, 0, 4002);
    assert_eq!(getresuid()?, old);
    case("credential_setresuid_updates_saved");

    let (notice, ready) = mpsc::channel();
    let sibling = thread::spawn(move || {
        ready.recv().unwrap();
        getresuid().unwrap()
    });
    setuid(UserId::new(65534)?)?;
    let unprivileged = ids(65534, 65534, 65534);
    assert_eq!(getresuid()?, unprivileged);
    assert_eq!(setfsuid_query()?, 65534);
    case("credential_setuid_drops_privileged_triplet");
    notice.send(())?;
    assert_eq!(sibling.join().unwrap(), old);
    case("credential_transition_is_calling_thread_only");

    assert!(setuid(UserId::new(0)?).unwrap_err().is_errno(EPERM));
    assert!(setgroups(&[]).unwrap_err().is_errno(EPERM));
    assert_eq!(getresuid()?, unprivileged);
    assert_eq!(getgroups(&mut supplementary)?, 2);
    assert_eq!(supplementary, [3101, 3102]);
    case("credential_post_drop_denials_preserve_state");
    Ok(())
}
