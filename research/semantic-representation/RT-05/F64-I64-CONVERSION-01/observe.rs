use std::hint::black_box;
use std::io::{self, Read};

fn checked(value: f64, require_integral: bool) -> String {
    let limit = (1_u64 << 63) as f64;
    if !value.is_finite() {
        "nonfinite".into()
    } else if value < -limit || value >= limit {
        "range".into()
    } else if require_integral && value.trunc() != value {
        "fraction".into()
    } else {
        format!("v{}", value as i64)
    }
}

fn main() {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input).unwrap();
    println!("{:016x}", (i64::MAX as f64).to_bits());
    for word in input.split_ascii_whitespace() {
        let value = black_box(f64::from_bits(u64::from_str_radix(word, 16).unwrap()));
        println!("{} {} v{}", checked(value, false), checked(value, true), value as i64);
    }
}
