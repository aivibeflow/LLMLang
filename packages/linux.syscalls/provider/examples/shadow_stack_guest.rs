use linux_syscalls_provider::*;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    assert!(std::env::args()
        .skip(1)
        .eq(["--llmlang-disposable-guest-probe"]));
    assert_eq!(getppid()?, 1, "run through the disposable guest init");

    let stack = map_shadow_stack(4097)?;
    assert_eq!(stack.as_slice().len(), 4097);
    assert!(stack.as_slice().iter().all(|&byte| byte == 0));
    let other = map_shadow_stack(1)?;
    assert_ne!(stack.as_slice().as_ptr(), other.as_slice().as_ptr());
    drop(stack);
    assert_eq!(other.as_slice(), [0]);
    drop(other);
    println!("LLMLANG_GUEST_CASE shadow_stack_guest_owns_zeroed_mappings_without_restore_tokens");
    Ok(())
}
