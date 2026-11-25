#[link(name = "owned")]
extern "C" {
    fn rt_apply(operation: u32, actor: u32, peer: u32, handle: u32, payload: u32) -> u32;
}

#[no_mangle]
pub extern "C" fn step(operation: u32, actor: u32, peer: u32, handle: u32, payload: u32) -> u32 {
    // The fixed-width arguments represent values and carry no borrowed pointers.
    unsafe { rt_apply(operation, actor, peer, handle, payload) }
}
