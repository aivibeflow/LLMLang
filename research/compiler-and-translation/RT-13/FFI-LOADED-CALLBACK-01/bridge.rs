use std::ffi::c_void;
use std::panic::{catch_unwind, set_hook};

#[repr(C)]
struct Context {
    peek: extern "C" fn(u32) -> i32,
    fail: i32,
}

#[no_mangle]
pub extern "C" fn initialize_bridge() {
    set_hook(Box::new(|_| {}));
}

#[no_mangle]
pub unsafe extern "C" fn bridge(raw: *const c_void, token: u32, value: i32) -> i32 {
    catch_unwind(|| {
        // The foreign owner keeps the exact C-compatible Context live through the join.
        let context = unsafe { &*raw.cast::<Context>() };
        let observed = (context.peek)(token);
        if observed < 0 {
            return observed;
        }
        if context.fail != 0 {
            panic!("injected callback failure");
        }
        observed + value
    })
    .unwrap_or(70)
}
