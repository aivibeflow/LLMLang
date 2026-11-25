use std::num::NonZeroU32;

#[repr(C)]
pub struct Tagged {
    tag: u32,
    bits: u32,
}

#[no_mangle]
pub extern "C" fn niche_identity(value: Option<NonZeroU32>) -> Option<NonZeroU32> {
    value
}

#[no_mangle]
pub extern "C" fn niche_is_present(value: Option<NonZeroU32>) -> u32 {
    u32::from(value.is_some())
}

#[no_mangle]
pub extern "C" fn inspect_tagged(value: Tagged) -> u64 {
    match (value.tag, value.bits) {
        (0, 0) => 0,
        (1, bits) => (1u64 << 32) | u64::from(bits),
        _ => 2u64 << 32,
    }
}

#[no_mangle]
pub extern "C" fn tagged_size() -> usize {
    std::mem::size_of::<Tagged>()
}

#[no_mangle]
pub extern "C" fn tagged_alignment() -> usize {
    std::mem::align_of::<Tagged>()
}

#[cfg(unrestricted)]
#[no_mangle]
pub extern "C" fn unsupported(value: Option<u32>) -> u32 {
    value.unwrap_or(0)
}

#[cfg(nested)]
#[no_mangle]
pub extern "C" fn unsupported(value: Option<Option<NonZeroU32>>) -> u32 {
    u32::from(value.is_some())
}
