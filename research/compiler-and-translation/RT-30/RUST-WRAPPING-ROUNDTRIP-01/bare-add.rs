fn main() {
    let left = std::hint::black_box(u32::MAX);
    let right = std::hint::black_box(1_u32);
    println!("{}", left + right);
}
