use linux_syscalls_provider::{
    create_file_page_mapping, remap_file_pages, SyscallError, FILE_MAPPING_PAGE_SIZE,
};

#[test]
fn remap_file_pages_replaces_readonly_owned_page() {
    let file_pages = [
        [0x19; FILE_MAPPING_PAGE_SIZE],
        [0x87; FILE_MAPPING_PAGE_SIZE],
    ];
    let mapping = create_file_page_mapping(&file_pages).unwrap();
    assert_eq!(mapping.as_slice(), file_pages[0]);
    let mapping = remap_file_pages(mapping, 1).unwrap();
    assert_eq!(mapping.as_slice(), file_pages[1]);
    let mapping = remap_file_pages(mapping, 0).unwrap();
    assert_eq!(mapping.as_slice(), file_pages[0]);
}

#[test]
fn remap_file_pages_rejects_indices_outside_owned_file() {
    assert!(matches!(
        create_file_page_mapping(&[]),
        Err(SyscallError::InvalidInput(_))
    ));
    let mapping = create_file_page_mapping(&[[0; FILE_MAPPING_PAGE_SIZE]]).unwrap();
    assert!(matches!(
        remap_file_pages(mapping, 1),
        Err(SyscallError::InvalidInput(_))
    ));
}
