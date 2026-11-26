use linux_syscalls_provider::*;

#[test]
fn bpf_array_checks_length_and_preserves_config_or_permission_errors() {
    for entries in [0, 1025] {
        assert!(matches!(
            bpf_map_create_u64(entries),
            Err(SyscallError::InvalidInput(_))
        ));
    }
    match bpf_map_create_u64(3) {
        Ok(mut map) => {
            assert_eq!(bpf_map_lookup_u64(&map, 0).unwrap(), 0);
            bpf_map_update_u64(&mut map, 1, 0x1122334455667788).unwrap();
            assert_eq!(bpf_map_lookup_u64(&map, 0).unwrap(), 0);
            assert_eq!(bpf_map_lookup_u64(&map, 1).unwrap(), 0x1122334455667788);
            assert!(matches!(
                bpf_map_lookup_u64(&map, 3),
                Err(SyscallError::InvalidInput(_))
            ));
            assert!(matches!(
                bpf_map_update_u64(&mut map, 3, 7),
                Err(SyscallError::InvalidInput(_))
            ));
        }
        Err(error) if error.is_errno(1) || error.is_errno(13) || error.is_errno(ENOSYS) => {}
        Err(error) => panic!("unexpected BPF map result: {error}"),
    }
}
