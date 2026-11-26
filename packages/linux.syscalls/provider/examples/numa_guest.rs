use linux_syscalls_provider::*;
use std::env;

fn case(name: &str) {
    println!("LLMLANG_GUEST_CASE {name}");
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    assert_eq!(
        env::args().nth(1).as_deref(),
        Some("--llmlang-disposable-guest-probe")
    );
    assert_eq!(getppid()?, 1, "run through the disposable guest init");

    let mask = NumaNodeMask::from_nodes(&[0])?;
    assert_eq!(get_mempolicy_allowed()?, mask);
    set_mempolicy(&NumaPolicy::Default)?;
    let initial = get_mempolicy()?;
    assert_eq!(initial.mode, 0);
    assert!(initial.nodes.is_empty());
    set_mempolicy(&NumaPolicy::Local)?;
    let local = get_mempolicy()?;
    assert_eq!(local.mode, 4);
    assert!(local.nodes.is_empty());
    set_mempolicy(&NumaPolicy::Interleave(mask.clone()))?;
    assert_eq!(
        get_mempolicy()?,
        NumaPolicyState {
            mode: 3,
            nodes: mask.clone()
        }
    );
    set_mempolicy(&NumaPolicy::Bind(mask.clone()))?;
    let thread_policy = get_mempolicy()?;
    assert_eq!(
        thread_policy,
        NumaPolicyState {
            mode: 2,
            nodes: mask.clone()
        }
    );
    case("numa_guest_observes_allowed_nodes_and_thread_policy");

    let mut mapping = mmap(4093, Protection::ReadWrite)?;
    mapping.as_mut_slice().unwrap()[..6].copy_from_slice(b"placed");
    assert_eq!(get_mempolicy_mapping(&mapping)?.mode, 0);
    mbind(&mut mapping, &NumaPolicy::Bind(mask.clone()))?;
    assert_eq!(get_mempolicy_mapping(&mapping)?, thread_policy);
    assert_eq!(&mapping.as_slice()[..6], b"placed");
    assert_eq!(get_mempolicy()?, thread_policy);
    mbind(&mut mapping, &NumaPolicy::Default)?;
    assert_eq!(get_mempolicy_mapping(&mapping)?.mode, 0);
    assert_eq!(&mapping.as_slice()[..6], b"placed");
    munmap(mapping)?;
    case("numa_guest_updates_only_owned_mapping_policy");

    let missing = NumaNodeMask::from_nodes(&[1023])?;
    assert!(set_mempolicy(&NumaPolicy::Bind(missing))
        .unwrap_err()
        .is_errno(EINVAL));
    assert_eq!(get_mempolicy()?, thread_policy);
    set_mempolicy(&NumaPolicy::Default)?;
    assert_eq!(get_mempolicy()?, initial);
    case("numa_guest_preserves_invalid_policy_errno");
    Ok(())
}
