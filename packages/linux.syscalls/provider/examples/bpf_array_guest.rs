//! Run in the disposable VM with CAP_BPF or CAP_SYS_ADMIN.
use linux_syscalls_provider::*;

fn main() -> Result<(), SyscallError> {
    let mut map = bpf_map_create_u64(3)?;
    assert_eq!(bpf_map_lookup_u64(&map, 0)?, 0);
    assert_eq!(bpf_map_lookup_u64(&map, 1)?, 0);
    println!("LLMLANG_GUEST_CASE bpf_array_initial_zero");

    bpf_map_update_u64(&mut map, 1, 0x1122_3344_5566_7788)?;
    assert_eq!(bpf_map_lookup_u64(&map, 0)?, 0);
    assert_eq!(bpf_map_lookup_u64(&map, 1)?, 0x1122_3344_5566_7788);
    assert_eq!(bpf_map_lookup_u64(&map, 2)?, 0);
    println!("LLMLANG_GUEST_CASE bpf_array_update_preserves_other_entries");

    assert!(matches!(
        bpf_map_lookup_u64(&map, 3),
        Err(SyscallError::InvalidInput(_))
    ));
    assert!(matches!(
        bpf_map_update_u64(&mut map, 3, 0),
        Err(SyscallError::InvalidInput(_))
    ));
    println!("LLMLANG_GUEST_CASE bpf_array_rejects_invalid_index");
    Ok(())
}
