pub struct Provider;

pub trait Decode {
    type Output;
    fn decode(&self, input: u8) -> Self::Output;
}

impl Decode for Provider {
    type Output = u16;

    fn decode(&self, input: u8) -> u16 {
        u16::from(input) + 256
    }
}
