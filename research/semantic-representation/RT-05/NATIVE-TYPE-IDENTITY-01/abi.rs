#![deny(improper_ctypes_definitions)]

#[repr(transparent)]
pub struct Quantity(u64, core::marker::PhantomData<()>);

#[repr(transparent)]
pub struct Nested(Quantity);

#[no_mangle]
pub extern "C" fn plain(value: u64) -> u64 {
    value.rotate_left(17) ^ 0x93ff_7ce3_ffa1_b923
}

#[no_mangle]
pub extern "C" fn wrapped(value: Quantity) -> Quantity {
    Quantity(plain(value.0), core::marker::PhantomData)
}

#[no_mangle]
pub extern "C" fn nested(value: Nested) -> Nested {
    Nested(wrapped(value.0))
}

#[no_mangle]
pub extern "C" fn quantity_size() -> usize {
    core::mem::size_of::<Quantity>()
}

#[no_mangle]
pub extern "C" fn quantity_alignment() -> usize {
    core::mem::align_of::<Quantity>()
}

#[no_mangle]
pub extern "C" fn nested_size() -> usize {
    core::mem::size_of::<Nested>()
}

#[no_mangle]
pub extern "C" fn nested_alignment() -> usize {
    core::mem::align_of::<Nested>()
}
