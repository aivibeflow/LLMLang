use std::slice;

#[no_mangle]
pub unsafe extern "C" fn mirror(seed: u64, data: *const u8, length: usize) -> u64 {
    if data.is_null() {
        return 1;
    }
    #[cfg(faulty)]
    let prime = 65_519;
    #[cfg(not(faulty))]
    let prime = 65_521;
    let mut a = seed & 0xffff;
    let mut b = seed >> 16;
    // The admitted C adapter supplies readable memory for exactly this length.
    for &byte in unsafe { slice::from_raw_parts(data, length) } {
        a = (a + u64::from(byte)) % prime;
        b = (b + a) % prime;
    }
    (b << 16) | a
}
