use linux_syscalls_provider::{getppid, ioperm_revoke, iopl_drop, modify_ldt_read};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    assert!(std::env::args()
        .skip(1)
        .eq(["--llmlang-disposable-guest-probe"]));
    assert_eq!(getppid()?, 1, "run through the disposable guest init");

    let mut output = [0xa5; 32];
    assert_eq!(modify_ldt_read(&mut output)?, 0);
    assert_eq!(output, [0xa5; 32]);
    println!("LLMLANG_GUEST_CASE modify_ldt_reads_empty_current_table");

    iopl_drop()?;
    iopl_drop()?;
    println!("LLMLANG_GUEST_CASE iopl_drop_succeeds_in_disposable_guest");

    ioperm_revoke(0, 65_536)?;
    ioperm_revoke(65_535, 1)?;
    println!("LLMLANG_GUEST_CASE ioperm_revokes_valid_guest_ranges");
    Ok(())
}
