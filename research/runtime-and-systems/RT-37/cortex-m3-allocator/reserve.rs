#![no_std]

const CAPACITY: u32 = 64;
const SLOT_SIZE: u32 = 16;
const FAILED: u32 = u32::MAX;

fn alignment_mask(alignment: u32) -> Option<u32> {
    let mask = alignment.wrapping_sub(1);
    if mask < SLOT_SIZE && alignment & mask == 0 {
        Some(mask)
    } else {
        None
    }
}

#[no_mangle]
pub unsafe extern "C" fn reserve_fixed(cursor: *mut u32, size: u32, alignment: u32) -> u32 {
    if size == 0 || size > SLOT_SIZE || alignment_mask(alignment).is_none() {
        return FAILED;
    }
    let current = unsafe { *cursor };
    if current >= CAPACITY || current % SLOT_SIZE != 0 {
        return FAILED;
    }
    // The largest admitted start is 48, leaving a complete slot at the end.
    unsafe { *cursor = current.wrapping_add(SLOT_SIZE) };
    current
}

#[no_mangle]
pub unsafe extern "C" fn reserve_bump(cursor: *mut u32, size: u32, alignment: u32) -> u32 {
    let Some(mask) = alignment_mask(alignment) else { return FAILED };
    if size == 0 || size > CAPACITY {
        return FAILED;
    }
    let current = unsafe { *cursor };
    if current > CAPACITY {
        return FAILED;
    }
    // The admitted cursor, alignment and size bound both additions.
    let start = current.wrapping_add(mask) & !mask;
    let end = start.wrapping_add(size);
    if end > CAPACITY {
        return FAILED;
    }
    unsafe { *cursor = end };
    start
}
