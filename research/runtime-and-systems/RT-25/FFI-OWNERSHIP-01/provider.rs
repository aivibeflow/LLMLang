use std::alloc::{GlobalAlloc, Layout, System};
use std::ffi::c_void;

extern "C" {
    fn malloc(size: usize) -> *mut c_void;
}

#[no_mangle]
pub extern "C" fn rust_system_malloc_address() -> *const c_void {
    malloc as *const c_void
}

#[no_mangle]
pub extern "C" fn rust_buffer_allocate(len: usize) -> *mut u8 {
    let Ok(layout) = Layout::array::<u8>(len) else {
        return std::ptr::null_mut();
    };
    if len == 0 {
        return std::ptr::null_mut();
    }
    unsafe { System.alloc_zeroed(layout) }
}

#[no_mangle]
pub unsafe extern "C" fn rust_buffer_release(ptr: *mut u8, len: usize) {
    // The C owner adapter supplies the same allocation and length.
    let layout = Layout::array::<u8>(len).expect("previously allocated length");
    unsafe { System.dealloc(ptr, layout) };
}

#[no_mangle]
pub unsafe extern "C" fn rust_borrow_digest(ptr: *const u8, len: usize) -> u64 {
    // The C adapter retains the allocation throughout the synchronous borrow.
    let bytes = unsafe { std::slice::from_raw_parts(ptr, len) };
    bytes.iter().fold(0, |digest, &byte| {
        digest.wrapping_mul(131).wrapping_add(u64::from(byte))
    })
}
