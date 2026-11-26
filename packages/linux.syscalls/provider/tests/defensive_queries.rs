use linux_syscalls_provider::*;
use std::fs;

const EPERM: i32 = 1;
const ENOENT: i32 = 2;
const EOPNOTSUPP: i32 = 95;
const MNT_UNIQUE_ID_OFFSET: u64 = 1 << 31;

fn unavailable(error: SyscallError) -> bool {
    [EPERM, ENOSYS, EOPNOTSUPP]
        .iter()
        .any(|code| error.is_errno(*code))
}

fn seccomp_status() -> Vec<String> {
    fs::read_to_string("/proc/thread-self/status")
        .unwrap_or_default()
        .lines()
        .filter(|line| line.starts_with("Seccomp"))
        .map(str::to_owned)
        .collect()
}

#[test]
fn seccomp_queries_report_actions_and_layout_without_installing_filter() {
    let before = seccomp_status();
    match seccomp_get_action_avail(SeccompAction::Allow) {
        Ok(()) => {
            for action in [
                SeccompAction::KillProcess,
                SeccompAction::KillThread,
                SeccompAction::Trap,
                SeccompAction::Errno,
                SeccompAction::UserNotify,
                SeccompAction::Trace,
                SeccompAction::Log,
            ] {
                seccomp_get_action_avail(action).unwrap();
            }
            assert_eq!(
                seccomp_get_notif_sizes().unwrap(),
                SeccompNotifSizes {
                    notification: 80,
                    response: 24,
                    data: 64,
                }
            );
        }
        Err(error) if unavailable(error) => {
            eprintln!("seccomp query is unavailable on this host: {error}");
        }
        Err(error) => panic!("unexpected seccomp error: {error}"),
    }
    assert_eq!(seccomp_status(), before);
}

#[test]
fn mount_queries_page_current_namespace_and_observe_basic_attributes() {
    let first = match listmount(0, 2) {
        Ok(first) => first,
        Err(error) if unavailable(error) => {
            eprintln!("listmount is unavailable on this host: {error}");
            return;
        }
        Err(error) => panic!("unexpected listmount error: {error}"),
    };
    assert!((1..=2).contains(&first.len()));
    assert!(first.iter().all(|id| *id > MNT_UNIQUE_ID_OFFSET));
    assert!(first.windows(2).all(|ids| ids[0] < ids[1]));
    let last = *first.last().unwrap();
    let next = listmount(last, 2).unwrap();
    assert!(next.iter().all(|id| *id > last));
    assert!(listmount(0, 0).unwrap().is_empty());
    for id in first {
        let basic = statmount(id).unwrap();
        assert_eq!(basic.mount_id, id);
        assert!(basic.parent_mount_id > MNT_UNIQUE_ID_OFFSET);
        assert!(basic.legacy_id > 0);
    }
}

#[test]
fn mount_queries_reject_invalid_inputs_and_preserve_kernel_errno() {
    assert!(matches!(
        listmount(0, 1025),
        Err(SyscallError::InvalidInput(_))
    ));
    assert!(matches!(
        listmount(u64::MAX, 1),
        Err(SyscallError::InvalidInput(_))
    ));
    if let Err(error) = listmount(0, 1) {
        assert!(unavailable(error), "{error}");
        return;
    }
    assert!(listmount(1, 1).unwrap_err().is_errno(EINVAL));
    assert!(statmount(0).unwrap_err().is_errno(EINVAL));
    assert!(statmount(u64::MAX - 1).unwrap_err().is_errno(ENOENT));
}
