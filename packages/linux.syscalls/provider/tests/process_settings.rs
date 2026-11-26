use linux_syscalls_provider::*;
use std::process::Command;

#[test]
fn resource_limit_changes_and_restores_inside_child() {
    const CHILD: &str = "LLMLANG_RLIMIT_SETTINGS_CHILD";
    if std::env::var_os(CHILD).is_none() {
        let output = Command::new(std::env::current_exe().unwrap())
            .args([
                "--exact",
                "resource_limit_changes_and_restores_inside_child",
            ])
            .env(CHILD, "1")
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "{}",
            String::from_utf8_lossy(&output.stdout)
        );
        return;
    }

    let resource = LimitResource::FileSize;
    let original = getrlimit(resource).unwrap();
    let target = match original.soft {
        Limit::Unlimited => 4096,
        Limit::Finite(soft) => soft.saturating_sub(1).min(4096),
    };
    let applied = Rlimit {
        soft: Limit::Finite(target),
        hard: original.hard,
    };
    setrlimit(resource, applied).unwrap();
    assert_eq!(getrlimit(resource).unwrap(), applied);
    for invalid in [
        Rlimit {
            soft: Limit::Unlimited,
            hard: Limit::Finite(3),
        },
        Rlimit {
            soft: Limit::Finite(u64::MAX),
            hard: Limit::Unlimited,
        },
    ] {
        assert!(matches!(
            setrlimit(resource, invalid),
            Err(SyscallError::InvalidInput(_))
        ));
    }
    assert_eq!(getrlimit(resource).unwrap(), applied);
    setrlimit(resource, original).unwrap();
    assert_eq!(getrlimit(resource).unwrap(), original);
}

#[test]
fn affinity_changes_only_the_calling_thread() {
    let original = sched_getaffinity().unwrap();
    let expected = original.clone();
    std::thread::spawn(move || {
        let current = sched_getaffinity().unwrap();
        assert_eq!(current, expected);
        let first = current.first().unwrap();
        assert!(current.contains(first));
        assert!(CpuAffinity::single(8192).is_err());
        let single = CpuAffinity::single(first).unwrap();
        sched_setaffinity(&single).unwrap();
        assert_eq!(sched_getaffinity().unwrap(), single);
        assert_eq!(getcpu().unwrap().cpu as usize, first);
        sched_setaffinity(&current).unwrap();
        assert_eq!(sched_getaffinity().unwrap(), current);
    })
    .join()
    .unwrap();
    assert_eq!(sched_getaffinity().unwrap(), original);
}
