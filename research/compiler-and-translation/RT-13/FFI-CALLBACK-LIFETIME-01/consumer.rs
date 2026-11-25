use std::ffi::{c_int, c_void};
use std::panic::catch_unwind;

type Callback = unsafe extern "C" fn(*mut c_void, u64, c_int, *mut c_void) -> c_int;

extern "C" {
    fn fixture_drive(call: Callback, context: *mut c_void, peer: *mut c_void,
                     payload: c_int, profile: c_int) -> c_int;
    fn fixture_thread(session: *mut c_void, ticket: u64, kind: *mut c_int) -> c_int;
    fn fixture_retire(session: *mut c_void, ticket: u64) -> c_int;
    fn fixture_finish(session: *mut c_void, ticket: u64, result: *mut c_int) -> c_int;
}

unsafe extern "C" fn rust_callback(
    session: *mut c_void,
    ticket: u64,
    payload: c_int,
    context: *mut c_void,
) -> c_int {
    let mut kind = 0;
    let mut ignored = 0;
    if unsafe { fixture_thread(session, ticket, &mut kind) } != 0
        || unsafe { fixture_retire(session, ticket) } != 2
        || unsafe { fixture_finish(session, ticket, &mut ignored) } != 2
    {
        return -88;
    }
    let offset = unsafe { *context.cast::<c_int>() };
    catch_unwind(|| {
        if payload == -7 {
            panic!("fixture callback failed");
        }
        kind * 1000 + payload * 3 + offset
    })
    .unwrap_or(-77)
}

fn main() {
    // The worker deliberately panics in some cases. The typed callback result
    // is the diagnostic for this short-lived fixture executable.
    std::panic::set_hook(Box::new(|_| {}));
    let mut values = std::env::args()
        .skip(1)
        .map(|arg| arg.parse::<c_int>().expect("fixture integer expected"));
    let payload = values.next().expect("payload");
    let profile = values.next().expect("profile");
    let mut offset = values.next().expect("offset");
    let mut peer = offset + 7;
    let status = unsafe {
        fixture_drive(
            rust_callback,
            (&mut offset as *mut c_int).cast(),
            (&mut peer as *mut c_int).cast(),
            payload,
            profile,
        )
    };
    std::process::exit(status);
}
