use std::hint::black_box;
use std::io::{self, Read};
use std::num::FpCategory;

fn main() {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input).unwrap();
    for word in input.split_ascii_whitespace() {
        let bits = u64::from_str_radix(word, 16).unwrap();
        let value = black_box(f64::from_bits(bits));
        let scalar = value.to_bits();
        let boxed = black_box([value])[0].to_bits();
        let class = match value.classify() {
            FpCategory::Nan => "nan",
            FpCategory::Infinite => "infinite",
            FpCategory::Zero => "zero",
            FpCategory::Subnormal => "subnormal",
            FpCategory::Normal => "normal",
        };
        let inverse = black_box(1.0 / value);
        let inverse_bits = if inverse.is_nan() { "nan".to_owned() } else { format!("{:016x}", inverse.to_bits()) };
        println!("{scalar:016x} {boxed:016x} {class} {} {inverse_bits}", !value.is_nan());
    }
}
