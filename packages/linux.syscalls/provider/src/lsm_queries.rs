use super::{abi, decode_nonnegative, decode_zero, SyscallError};
use std::mem::size_of;

const LSM_GET_SELF_ATTR: usize = 459;
const LSM_SET_SELF_ATTR: usize = 460;
const LSM_LIST_MODULES: usize = 461;
const LSM_ATTR_CURRENT: usize = 100;
const LSM_ID_APPARMOR: u64 = 104;
const APPARMOR_CHECK: [u8; 23] = *b"permprofile unconfined\0";
const E2BIG: i32 = 7;
const MAX_MODULE_BYTES: u32 = 2048;
const MAX_CONTEXT_BYTES: u32 = 65_536;
const CONTEXT_HEADER_BYTES: usize = 32;

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum LsmQuery<T> {
    Complete(T),
    /// The kernel supplied both E2BIG and a larger required byte count.
    BufferTooSmall {
        required_bytes: u32,
        errno: SyscallError,
    },
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct LsmContext {
    pub module_id: u64,
    /// Module-specific flag bits, preserved as returned.
    pub flags: u64,
    /// Opaque context bytes, including any terminator in the reported value.
    pub value: Vec<u8>,
}

fn decode_query<T>(
    raw: isize,
    capacity: u32,
    reported: u32,
    parse: impl FnOnce(usize, usize) -> Result<T, SyscallError>,
) -> Result<LsmQuery<T>, SyscallError> {
    match decode_nonnegative(raw) {
        Ok(count) if reported <= capacity => {
            Ok(LsmQuery::Complete(parse(count, reported as usize)?))
        }
        Ok(_) => Err(SyscallError::UnexpectedReturn(raw)),
        Err(errno) if errno.is_errno(E2BIG) && reported > capacity => {
            Ok(LsmQuery::BufferTooSmall {
                required_bytes: reported,
                errno,
            })
        }
        Err(error) => Err(error),
    }
}

/// Observe active LSM IDs in kernel order. The capacity is in bytes
/// and is limited to 2048. Callers choose whether to retry E2BIG.
pub fn lsm_list_modules(capacity_bytes: u32) -> Result<LsmQuery<Vec<u64>>, SyscallError> {
    if capacity_bytes > MAX_MODULE_BYTES {
        return Err(SyscallError::InvalidInput(
            "LSM module capacity exceeds 2048 bytes",
        ));
    }
    let mut modules = vec![0_u64; (capacity_bytes as usize).div_ceil(size_of::<u64>())];
    let mut reported_bytes = capacity_bytes;
    let raw = unsafe {
        abi::call(
            LSM_LIST_MODULES,
            [
                modules.as_mut_ptr() as usize,
                (&mut reported_bytes as *mut u32) as usize,
                0,
                0,
                0,
                0,
            ],
        )
    };
    decode_query(raw, capacity_bytes, reported_bytes, |count, reported| {
        if count.checked_mul(size_of::<u64>()) != Some(reported) {
            return Err(SyscallError::UnexpectedReturn(raw));
        }
        modules.truncate(count);
        Ok(modules)
    })
}

/// Observe LSM_ATTR_CURRENT for the calling thread. Only reported context
/// bytes are returned. No module-specific meaning is assigned by this API.
pub fn lsm_get_self_attr(capacity_bytes: u32) -> Result<LsmQuery<Vec<LsmContext>>, SyscallError> {
    if capacity_bytes > MAX_CONTEXT_BYTES {
        return Err(SyscallError::InvalidInput(
            "LSM context capacity exceeds 65536 bytes",
        ));
    }
    let mut output = vec![0_u8; capacity_bytes as usize];
    let mut reported_bytes = capacity_bytes;
    let raw = unsafe {
        abi::call(
            LSM_GET_SELF_ATTR,
            [
                LSM_ATTR_CURRENT,
                output.as_mut_ptr() as usize,
                (&mut reported_bytes as *mut u32) as usize,
                0,
                0,
                0,
            ],
        )
    };
    decode_query(raw, capacity_bytes, reported_bytes, |count, reported| {
        parse_contexts(&output[..reported], count, raw)
    })
}

#[repr(C)]
struct AppArmorCheck {
    id: u64,
    flags: u64,
    len: u64,
    ctx_len: u64,
    command: [u8; APPARMOR_CHECK.len()],
    padding: u8,
}

const _: () = {
    assert!(std::mem::offset_of!(AppArmorCheck, command) == CONTEXT_HEADER_BYTES);
    assert!(size_of::<AppArmorCheck>() == 56);
};

fn is_unconfined_apparmor(context: &LsmContext) -> bool {
    context.module_id == LSM_ID_APPARMOR && context.flags == 0 && context.value == b"unconfined"
}

/// Checks the calling thread's existing unconfined AppArmor profile using
/// AppArmor's permission-only command. No profile transition is performed.
pub fn lsm_set_self_attr() -> Result<(), SyscallError> {
    let contexts = match lsm_get_self_attr(MAX_CONTEXT_BYTES)? {
        LsmQuery::Complete(contexts) => contexts,
        LsmQuery::BufferTooSmall { errno, .. } => return Err(errno),
    };
    if !contexts.iter().any(is_unconfined_apparmor) {
        return Err(SyscallError::InvalidInput(
            "the calling thread must have the unconfined AppArmor profile",
        ));
    }

    let check = AppArmorCheck {
        id: LSM_ID_APPARMOR,
        flags: 0,
        len: size_of::<AppArmorCheck>() as u64,
        ctx_len: APPARMOR_CHECK.len() as u64,
        command: APPARMOR_CHECK,
        padding: 0,
    };
    decode_zero(unsafe {
        abi::call(
            LSM_SET_SELF_ATTR,
            [
                LSM_ATTR_CURRENT,
                (&check as *const AppArmorCheck) as usize,
                size_of::<AppArmorCheck>(),
                0,
                0,
                0,
            ],
        )
    })
}

fn context_word(bytes: &[u8]) -> u64 {
    u64::from_ne_bytes(bytes.try_into().expect("exactly one native word"))
}

fn parse_contexts(
    mut bytes: &[u8],
    count: usize,
    raw: isize,
) -> Result<Vec<LsmContext>, SyscallError> {
    let malformed = SyscallError::UnexpectedReturn(raw);
    if count > bytes.len() / CONTEXT_HEADER_BYTES {
        return Err(malformed);
    }
    let mut contexts = Vec::with_capacity(count);
    for _ in 0..count {
        let Some(header) = bytes.get(..CONTEXT_HEADER_BYTES) else {
            return Err(malformed);
        };
        let module_id = context_word(&header[..8]);
        let flags = context_word(&header[8..16]);
        let record_len = usize::try_from(context_word(&header[16..24])).map_err(|_| malformed)?;
        let value_len = usize::try_from(context_word(&header[24..32])).map_err(|_| malformed)?;
        if module_id == 0
            || record_len < CONTEXT_HEADER_BYTES
            || record_len % size_of::<usize>() != 0
            || record_len > bytes.len()
            || value_len > record_len - CONTEXT_HEADER_BYTES
        {
            return Err(malformed);
        }
        contexts.push(LsmContext {
            module_id,
            flags,
            value: bytes[CONTEXT_HEADER_BYTES..CONTEXT_HEADER_BYTES + value_len].to_vec(),
        });
        bytes = &bytes[record_len..];
    }
    if !bytes.is_empty() {
        return Err(malformed);
    }
    Ok(contexts)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn lsm_recheck_requires_exact_unconfined_apparmor_context() {
        let context = LsmContext {
            module_id: LSM_ID_APPARMOR,
            flags: 0,
            value: b"unconfined".to_vec(),
        };
        assert!(is_unconfined_apparmor(&context));
        for input in [
            LsmContext {
                module_id: 100,
                ..context.clone()
            },
            LsmContext {
                flags: 1,
                ..context.clone()
            },
            LsmContext {
                value: b"unconfined\0".to_vec(),
                ..context.clone()
            },
            LsmContext {
                value: b"other (enforce)".to_vec(),
                ..context
            },
        ] {
            assert!(!is_unconfined_apparmor(&input));
        }
    }

    #[test]
    fn lsm_context_parser_rejects_inconsistent_native_records() {
        let mut record = [0_u8; 40];
        record[..8].copy_from_slice(&104_u64.to_ne_bytes());
        record[8..16].copy_from_slice(&0xa5_u64.to_ne_bytes());
        record[16..24].copy_from_slice(&40_u64.to_ne_bytes());
        record[24..32].copy_from_slice(&3_u64.to_ne_bytes());
        record[32..35].copy_from_slice(&[0xff, 0, 0xac]);
        record[35..].fill(0xee);
        assert_eq!(
            parse_contexts(&record, 1, 1).unwrap(),
            [LsmContext {
                module_id: 104,
                flags: 0xa5,
                value: vec![0xff, 0, 0xac]
            }]
        );

        for invalid_length in [0, 31, 39, 48, u64::MAX] {
            let mut malformed = record;
            malformed[16..24].copy_from_slice(&invalid_length.to_ne_bytes());
            assert!(parse_contexts(&malformed, 1, 1).is_err());
        }
        let mut malformed = record;
        malformed[24..32].copy_from_slice(&9_u64.to_ne_bytes());
        assert!(parse_contexts(&malformed, 1, 1).is_err());
        assert!(parse_contexts(&record, 2, 2).is_err());
        assert!(parse_contexts(&record, 0, 0).is_err());
    }

    #[test]
    fn lsm_query_keeps_unsized_errno_separate_from_capacity_response() {
        assert!(matches!(
            decode_query(-7, 4, 8, |_, _| Ok(())),
            Ok(LsmQuery::BufferTooSmall { required_bytes: 8, errno }) if errno.is_errno(7)
        ));
        assert!(decode_query(-7, 4, 4, |_, _| Ok(()))
            .unwrap_err()
            .is_errno(7));
        assert_eq!(
            decode_query(1, 4, 8, |_, _| Ok(())).unwrap_err(),
            SyscallError::UnexpectedReturn(1)
        );
    }
}
