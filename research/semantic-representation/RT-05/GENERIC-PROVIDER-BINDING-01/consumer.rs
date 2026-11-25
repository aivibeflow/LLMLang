use routes_provider::{dictionary, trait_provider, Amber, Cobalt, Rule};

#[inline(never)]
fn specialized_inline<T: Rule>(rule: &T, value: i64) -> i64 {
    rule.apply(value)
}

#[no_mangle]
pub extern "C" fn route_static(tag: u8, value: i64) -> i64 {
    if tag == 0 {
        specialized_inline(&Amber, value)
    } else {
        specialized_inline(&Cobalt, value)
    }
}

#[inline(never)]
fn specialized_linked<T: Rule>(rule: &T, value: i64) -> i64 {
    rule.apply_linked(value)
}

#[no_mangle]
pub extern "C" fn route_linked(tag: u8, value: i64) -> i64 {
    if tag == 0 {
        specialized_linked(&Amber, value)
    } else {
        specialized_linked(&Cobalt, value)
    }
}

#[no_mangle]
pub extern "C" fn route_trait(tag: u8, value: i64) -> i64 {
    trait_provider(tag).apply(value)
}

#[no_mangle]
pub extern "C" fn route_dictionary(tag: u8, value: i64) -> i64 {
    (dictionary(tag).apply)(value)
}
