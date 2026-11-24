#![no_std]

#[no_mangle]
pub extern "C" fn step(previous: u32, sample: u32, valid: u32) -> u32 {
    if valid != 1 || sample >= 100 {
        return 0;
    }
    let previous = previous.min(255);
    if sample >= 80 {
        previous.saturating_add(13).min(255)
    } else if sample < 20 {
        previous.saturating_sub(9)
    } else {
        previous
    }
}
