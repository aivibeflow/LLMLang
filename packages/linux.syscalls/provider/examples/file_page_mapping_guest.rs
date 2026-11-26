//! Exercise whole-page remapping on the pinned guest Linux ABI.
use linux_syscalls_provider::{
    create_file_page_mapping, getppid, remap_file_pages, restart_syscall, EINTR,
    FILE_MAPPING_PAGE_SIZE,
};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    assert!(std::env::args()
        .skip(1)
        .eq(["--llmlang-disposable-guest-probe"]));
    assert_eq!(getppid()?, 1, "run through the disposable guest init");
    let file_pages = [
        [0x19; FILE_MAPPING_PAGE_SIZE],
        [0x87; FILE_MAPPING_PAGE_SIZE],
    ];
    let mapping = create_file_page_mapping(&file_pages)?;
    assert_eq!(mapping.as_slice(), file_pages[0]);
    let mapping = remap_file_pages(mapping, 1)?;
    assert_eq!(mapping.as_slice(), file_pages[1]);
    let mapping = remap_file_pages(mapping, 0)?;
    assert_eq!(mapping.as_slice(), file_pages[0]);
    println!("LLMLANG_GUEST_CASE remap_file_pages_replaces_readonly_owned_page");
    assert!(std::thread::spawn(restart_syscall)
        .join()
        .unwrap()
        .unwrap_err()
        .is_errno(EINTR));
    println!("LLMLANG_GUEST_CASE restart_syscall_preserves_inactive_thread_eintr");
    Ok(())
}
