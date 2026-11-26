use linux_syscalls_provider::*;

const ENOENT: i32 = 2;
const EOPNOTSUPP: i32 = 95;
const PAGE_SIZE: usize = 4096;

fn case(name: &str) {
    println!("LLMLANG_GUEST_CASE {name}");
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    assert!(std::env::args()
        .skip(1)
        .eq(["--llmlang-disposable-guest-probe"]));
    assert_eq!(getppid()?, 1, "run through the disposable guest init");

    let allowed = get_mempolicy_allowed()?;
    let node0 = NumaNodeMask::from_nodes(&[0])?;
    let node1 = NumaNodeMask::from_nodes(&[1])?;
    let both = NumaNodeMask::from_nodes(&[0, 1])?;
    assert!(allowed == node0 || allowed == both);

    let mut mapping = mmap(PAGE_SIZE + 1, Protection::ReadWrite)?;
    assert!(set_mempolicy_home_node(&mut mapping, 0)
        .unwrap_err()
        .is_errno(ENOENT));
    mbind(&mut mapping, &NumaPolicy::Interleave(allowed.clone()))?;
    assert!(set_mempolicy_home_node(&mut mapping, 0)
        .unwrap_err()
        .is_errno(EOPNOTSUPP));
    case("numa_guest_home_node_preserves_policy_errnos");

    mbind(&mut mapping, &NumaPolicy::Bind(allowed.clone()))?;
    set_mempolicy_home_node(&mut mapping, 0)?;
    mapping.as_mut_slice().unwrap()[0] = 37;
    let statuses = move_pages(&mapping, &[PAGE_SIZE, 0, 0])?;
    assert_eq!(statuses[0].unwrap_err().code(), ENOENT);
    assert_eq!(statuses[1..], [Ok(0), Ok(0)]);
    case("numa_guest_queries_owned_pages_in_order_with_per_page_errno");

    let (home, target) = if allowed == both {
        (1, &node1)
    } else {
        (0, &node0)
    };
    set_mempolicy_home_node(&mut mapping, home)?;
    let policy = get_mempolicy_mapping(&mapping)?;
    assert_eq!(policy.mode, 2);
    assert_eq!(policy.nodes, allowed);
    mapping.as_mut_slice().unwrap()[PAGE_SIZE] = 51;
    assert_eq!(move_pages(&mapping, &[PAGE_SIZE, 0])?, [Ok(home), Ok(0)]);
    assert_eq!(mapping.as_slice()[0], 37);
    assert_eq!(mapping.as_slice()[PAGE_SIZE], 51);
    case("numa_guest_home_node_applies_to_owned_bind_policy");

    assert_eq!(migrate_pages(&node0, &node0)?, 0);
    assert_eq!(move_pages(&mapping, &[0])?, [Ok(0)]);
    let disallowed = NumaNodeMask::from_nodes(&[1023])?;
    for (from, to) in [(&disallowed, target), (&node0, &disallowed)] {
        assert!(matches!(
            migrate_pages(from, to),
            Err(SyscallError::InvalidInput(_))
        ));
    }
    case("numa_guest_migrate_pages_checks_allowed_masks");

    if home != 0 {
        assert_eq!(migrate_pages(&node0, target)?, 0);
        assert_eq!(move_pages(&mapping, &[0, PAGE_SIZE])?, [Ok(home), Ok(home)]);
        assert_eq!(mapping.as_slice()[0], 37);
        assert_eq!(mapping.as_slice()[PAGE_SIZE], 51);
        case("numa_guest_migrates_current_process_between_nodes");
    }

    munmap(mapping)?;
    Ok(())
}
