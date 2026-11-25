pub struct Provider;

pub trait Decode<Output> {
    fn decode(&self, input: u8) -> Output;
}

impl Decode<u8> for Provider {
    fn decode(&self, input: u8) -> u8 {
        input.wrapping_add(1)
    }
}

impl Decode<u16> for Provider {
    fn decode(&self, input: u8) -> u16 {
        u16::from(input) + 256
    }
}
