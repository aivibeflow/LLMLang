use linux_syscalls_provider::*;

fn main() -> Result<(), SyscallError> {
    assert_eq!(
        std::env::args().nth(1).as_deref(),
        Some("--llmlang-disposable-guest-probe")
    );
    assert_eq!(getppid()?, 1, "run through the disposable guest init");

    let source = [3, 0, 255, 7, 9];
    let cases = [
        (
            process_vm_readv as fn(&[u8], &mut [u8]) -> _,
            "self_memory_guest_reads_exact_prefix",
        ),
        (process_vm_writev, "self_memory_guest_writes_exact_prefix"),
    ];
    for (transfer, case) in cases {
        let mut longer = [0x55; 8];
        assert_eq!(transfer(&source, &mut longer)?, 5);
        assert_eq!(longer, [3, 0, 255, 7, 9, 0x55, 0x55, 0x55]);
        assert_eq!(transfer(&[], &mut longer)?, 0);
        assert_eq!(longer, [3, 0, 255, 7, 9, 0x55, 0x55, 0x55]);
        assert_eq!(transfer(&source, &mut [])?, 0);
        let mut shorter = [0x55; 2];
        assert_eq!(transfer(&source, &mut shorter)?, 2);
        assert_eq!(shorter, [3, 0]);
        println!("LLMLANG_GUEST_CASE {case}");
    }
    assert_eq!(source, [3, 0, 255, 7, 9]);
    Ok(())
}
