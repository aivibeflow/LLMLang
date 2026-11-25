use std::slice;
use std::str;

/// The caller supplies a valid non-null span of the indicated length.
#[no_mangle]
pub unsafe extern "C" fn utf8_scalar_count(input: *const u8, length: usize) -> usize {
    // SAFETY: The foreign caller owns an initialized span for this call.
    let payload = unsafe { slice::from_raw_parts(input, length) };
    match str::from_utf8(payload) {
        Ok(text) => text.chars().count(),
        Err(_) => usize::MAX,
    }
}
