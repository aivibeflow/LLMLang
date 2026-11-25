#[derive(Copy, Clone)]
pub struct Below<const LIMIT: u16>(u16);

#[derive(Debug)]
pub enum Failure {
    Source,
    Overflow,
    Destination,
}

impl<const LIMIT: u16> Below<LIMIT> {
    pub fn new(raw: u16) -> Option<Self> {
        (raw < LIMIT).then_some(Self(raw))
    }

    pub fn raw(self) -> u16 {
        self.0
    }

    pub fn advance<const NEXT: u16>(self, delta: u16) -> Result<Below<NEXT>, Failure> {
        let raised = self.0.checked_add(delta).ok_or(Failure::Overflow)?;
        Below::<NEXT>::new(raised).ok_or(Failure::Destination)
    }
}

pub fn checked<const BEFORE: u16, const AFTER: u16>(raw: u16, delta: u16)
    -> Result<u16, Failure>
{
    Below::<BEFORE>::new(raw)
        .ok_or(Failure::Source)?
        .advance::<AFTER>(delta)
        .map(Below::raw)
}
