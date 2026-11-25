pub struct Provider;

pub trait Decode<Input> {
    type Output;
    fn decode(&self, input: Input) -> Self::Output;
}

impl Decode<u8> for Provider {
    type Output = u8;

    fn decode(&self, input: u8) -> u8 {
        input.wrapping_add(1)
    }
}

impl Decode<u16> for Provider {
    type Output = u16;

    fn decode(&self, input: u16) -> u16 {
        input + 256
    }
}
