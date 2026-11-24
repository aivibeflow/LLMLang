#![no_std]

#[no_mangle]
pub unsafe extern "C" fn sample_pair(csr: *const u32) -> u32 {
    let first = unsafe { core::ptr::read_volatile(csr) };
    let second = unsafe { core::ptr::read_volatile(csr) };
    ((first >> 15) & 2) | ((second >> 16) & 1)
}
