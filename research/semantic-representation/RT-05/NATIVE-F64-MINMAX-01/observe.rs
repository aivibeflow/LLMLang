use std::hint::black_box;
use std::io::{self, Read};

fn main() {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input).unwrap();
    let mut words = input.split_ascii_whitespace();
    while let Some(a) = words.next() {
        let left = black_box(f64::from_bits(u64::from_str_radix(a, 16).unwrap()));
        let right = black_box(f64::from_bits(u64::from_str_radix(words.next().unwrap(), 16).unwrap()));
        println!("{:016x} {:016x}", left.min(right).to_bits(), left.max(right).to_bits());
    }
}
