use std::io::{self, BufRead};

extern "C" {
    fn checked_add(input: u64, enabled: u32, slot: *mut u64) -> u32;
}

fn main() {
    for line in io::stdin().lock().lines() {
        let line = line.unwrap();
        let (left, right) = line.split_once(' ').unwrap();
        let mut output = 0xabad1234abcdef01u64;
        // The initialized slot remains uniquely writable through this call.
        let status = unsafe { checked_add(left.parse().unwrap(), right.parse().unwrap(), &mut output) };
        println!("{status} {output}");
    }
}
