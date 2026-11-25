#[repr(C)]
#[derive(Clone, Copy)]
struct Pair {
    x: u64,
    y: u64,
}

#[cfg(all(not(bridge), not(win)))]
extern "sysv64" {
    fn transform_record(input: Pair, salt: u64) -> Pair;
}

#[cfg(all(not(bridge), win))]
extern "win64" {
    fn transform_record(input: Pair, salt: u64) -> Pair;
}

extern "C" {
    fn provider_call_style() -> u32;
    #[cfg(bridge)]
    fn bridge_record(input: *const Pair, salt: u64, output: *mut Pair);
}

fn main() {
    let values_x = [0, 1, 4_294_967_297, u64::MAX];
    let values_y = [0, 2, 1_099_511_627_779, u64::MAX];
    let salts = [0, 3, 9_223_372_036_854_775_807, u64::MAX];

    println!("[{},{},{},{},{}]", std::mem::size_of::<Pair>(), std::mem::align_of::<Pair>(),
             std::mem::offset_of!(Pair, x), std::mem::offset_of!(Pair, y),
             unsafe { provider_call_style() });
    for x in values_x {
        for y in values_y {
            for salt in salts {
                let input = Pair { x, y };
                #[cfg(not(bridge))]
                // The source declaration is selected from the provider's explicit build profile.
                let output = unsafe { transform_record(input, salt) };
                #[cfg(bridge)]
                let output = {
                    let mut value = Pair { x: 0, y: 0 };
                    // Both pointers stay live across the fixed C bridge invocation.
                    unsafe { bridge_record(&input, salt, &mut value) };
                    value
                };
                println!("[{},{}]", output.x, output.y);
            }
        }
    }
}
