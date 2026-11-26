// Linux enters _start with no return address. Align rsp for a System V call.
core::arch::global_asm!(
    ".global _start",
    ".type _start,@function",
    "_start:",
    "xor ebp, ebp",
    "and rsp, -16",
    "call {entry}",
    "ud2",
    ".size _start, .-_start",
    entry = sym llmlang_entry,
);

extern "C" fn llmlang_entry() -> ! {
    // Match Rust's command-line behavior: a broken pipe returns EPIPE.
    // Linux x86-64 struct sigaction: handler, flags, restorer, signal mask.
    let ignore_sigpipe = [1usize, 0, 0, 0];
    let result = unsafe { raw_syscall(13, [13, ignore_sigpipe.as_ptr() as usize, 0, 8, 0, 0]) };
    if result < 0 {
        exit_process(1);
    }
    exit_process(llmlang_main())
}

#[panic_handler]
fn panic(_: &core::panic::PanicInfo<'_>) -> ! {
    exit_process(101)
}

fn exit_process(status: ExitStatus) -> ! {
    unsafe {
        asm!(
            "syscall",
            "ud2",
            in("rax") 231usize, // exit_group
            in("rdi") status as usize,
            options(noreturn, nostack),
        )
    }
}
