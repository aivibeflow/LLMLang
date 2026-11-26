#[path = "../src/syscall_lowering.rs"]
mod syscall_lowering;

use syscall_lowering::{lower, lower_native};

const OPEN: &str = include_str!("../src/open.llmlang");

#[test]
fn lowers_typed_syscall_operands_to_linux_abi_words() {
    let rust = lower(OPEN).unwrap();
    assert!(rust.contains("abi::invoke(abi::OPEN, [path.as_ptr() as usize,"));
    assert!(
        rust.contains("abi::invoke(abi::OPENAT, [directory.argument(), path.as_ptr() as usize,")
    );
    assert!(rust.contains("options.flags as usize, options.mode as usize"));
}

#[test]
fn rejects_unknown_entries_and_invalid_syscall_operands() {
    for (source, expected) in [
        (
            OPEN.replace("syscall(open,", "syscall(2,"),
            "unsupported native syscall",
        ),
        (
            OPEN.replace("syscall(open,", "syscall(openat,"),
            "does not match",
        ),
        (
            OPEN.replace("options.flags", "options.flags | O_CLOEXEC"),
            "invalid syscall operand",
        ),
        (
            OPEN.replace("options.mode)", "options.mode, path)"),
            "too many syscall operands",
        ),
    ] {
        assert!(lower(&source).unwrap_err().contains(expected));
    }
}

#[test]
fn lowers_native_table_and_rejects_duplicate_or_callable_continuations() {
    let source = include_str!("../src/native.llmlang");
    let rust = lower_native(source).unwrap();
    assert_eq!(rust.matches("=> unsafe { native_").count(), 355);
    assert!(rust.contains("0 => unsafe { native_read(words[0], words[1], words[2]) }"));
    assert!(rust.contains("enter::<2>([arg_path, arg_flags, arg_mode, 0, 0, 0])"));
    assert!(rust.contains("enter::<9>([arg_addr, arg_len, arg_prot, arg_flags, arg_fd, arg_off])"));
    assert!(rust.contains("enter::<39>([0, 0, 0, 0, 0, 0])"));
    assert!(!rust.contains("15 => unsafe { native_rt_sigreturn"));
    assert!(rust.contains("fn vfork_exec("));
    assert!(rust.contains("llmlang_fixed_signal_restorer:"));
    assert!(lower_native(
        &source.replace("syscall(1, fd, buf, count)", "syscall(0, fd, buf, count)")
    )
    .unwrap_err()
    .contains("duplicate"));
    assert!(lower_native(&source.replace(
        "restorer fn rt_sigreturn() -> Never {\n    syscall(15); trap()\n}",
        "unsafe fn rt_sigreturn() -> AbiResult { syscall(15) }",
    ))
    .unwrap_err()
    .contains("dedicated continuation"));
    assert!(lower_native(&source.replace(
        "syscall(2, path, flags, mode)",
        "syscall(2, path, mode, flags)"
    ))
    .unwrap_err()
    .contains("declared parameter order"));
}
