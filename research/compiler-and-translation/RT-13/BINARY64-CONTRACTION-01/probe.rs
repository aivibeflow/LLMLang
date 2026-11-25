use std::io::{self, BufRead};

fn main() -> io::Result<()> {
    for line in io::stdin().lock().lines() {
        let line = line?;
        let [a, b, c]: [f64; 3] = line
            .split_whitespace()
            .map(|field| f64::from_bits(u64::from_str_radix(field, 16).unwrap()))
            .collect::<Vec<_>>()
            .try_into()
            .unwrap();
        println!("{:016x} {:016x}", (a * b + c).to_bits(), a.mul_add(b, c).to_bits());
    }
    Ok(())
}
