#[repr(C)]
struct NativeOutcome {
    disposition: u32,
    usable_token: u32,
}

const _: () = assert!(std::mem::size_of::<NativeOutcome>() == 8);
const _: () = assert!(std::mem::offset_of!(NativeOutcome, usable_token) == 4);

extern "C" {
    fn rt_begin(consume_unknown: u32);
    fn rt_acquire(slot: u32, source: u32, destination: u32) -> u32;
    fn rt_release(token: u32, disposition: u32) -> NativeOutcome;
    fn rt_finish() -> u64;
}

fn acquire(slot: u32, roles: Roles) -> Option<u32> {
    // The fixture provider owns its descriptor table. Only a nonzero token grants use.
    let result = unsafe { rt_acquire(slot, u32::from(roles.0), u32::from(roles.1)) };
    (result != 0).then_some(result)
}

fn release(token: u32, scripted: Disposition) -> Disposition {
    let request = match scripted {
        Disposition::Ok => 0,
        Disposition::RetainedError => 1,
        Disposition::ConsumedError => 2,
        Disposition::Indeterminate => 3,
    };
    let native = unsafe { rt_release(token, request) };
    let outcome = match native.disposition {
        0 => Disposition::Ok,
        1 => Disposition::RetainedError,
        2 => Disposition::ConsumedError,
        3 => Disposition::Indeterminate,
        value => panic!("unsupported foreign disposition {value}"),
    };
    assert_eq!(
        native.usable_token,
        if outcome == Disposition::RetainedError { token } else { 0 },
    );
    outcome
}
