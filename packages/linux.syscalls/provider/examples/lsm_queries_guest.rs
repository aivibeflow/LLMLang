use linux_syscalls_provider::*;
use std::env;

const E2BIG: i32 = 7;
const LSM_ID_APPARMOR: u64 = 104;
const LSM_ID_LANDLOCK: u64 = 110;

fn case(name: &str) {
    println!("LLMLANG_GUEST_CASE {name}");
}

fn size<T>(query: LsmQuery<T>) -> u32 {
    let LsmQuery::BufferTooSmall {
        required_bytes,
        errno,
    } = query
    else {
        panic!("guest profile expected at least one kernel entry")
    };
    assert!(required_bytes > 0);
    assert!(errno.is_errno(E2BIG));
    required_bytes
}

fn complete<T>(query: LsmQuery<T>) -> T {
    let LsmQuery::Complete(result) = query else {
        panic!("previously reported capacity should fit")
    };
    result
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    assert_eq!(
        env::args().nth(1).as_deref(),
        Some("--llmlang-disposable-guest-probe")
    );
    assert_eq!(getppid()?, 1, "run through the disposable guest init");

    let module_bytes = size(lsm_list_modules(0)?);
    let modules = complete(lsm_list_modules(module_bytes)?);
    assert_eq!(modules.len() * 8, module_bytes as usize);
    assert_eq!(complete(lsm_list_modules(module_bytes + 1)?), modules);
    assert!(modules.contains(&LSM_ID_LANDLOCK));
    println!("Observed {} guest LSM modules", modules.len());
    case("lsm_guest_lists_modules_and_reports_required_capacity");

    let context_bytes = size(lsm_get_self_attr(0)?);
    let contexts = complete(lsm_get_self_attr(context_bytes)?);
    assert!(!contexts.is_empty());
    assert!(contexts
        .iter()
        .all(|context| { modules.contains(&context.module_id) && !context.value.is_empty() }));
    println!("Observed {} guest current LSM contexts", contexts.len());
    case("lsm_guest_reads_bounded_current_contexts");

    assert!(contexts.iter().any(|context| {
        context.module_id == LSM_ID_APPARMOR && context.flags == 0 && context.value == b"unconfined"
    }));
    lsm_set_self_attr()?;
    assert_eq!(complete(lsm_get_self_attr(context_bytes)?), contexts);
    case("lsm_guest_rechecks_own_apparmor_profile_without_transition");
    Ok(())
}
