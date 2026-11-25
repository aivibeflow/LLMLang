#[repr(transparent)]
pub struct Ticks(u16);

#[repr(transparent)]
pub struct Millis(u16);

pub trait Provider {
    type Output;
    fn reading(&self, raw: u8) -> Self::Output;
}

impl Ticks {
    pub fn raw(self) -> u16 {
        self.0
    }
}

macro_rules! provider {
    ($name:ident, $abi:ident, $kind:ident, $raw:ident, $value:expr) => {
        pub struct $name;

        impl Provider for $name {
            type Output = $kind;

            fn reading(&self, input: u8) -> $kind {
                let $raw = u16::from(input);
                $kind($value)
            }
        }

        #[no_mangle]
        pub extern "C" fn $abi(input: u8) -> $kind {
            $name.reading(input)
        }
    };
}

provider!(Identity, ticks_identity, Ticks, raw, raw);
provider!(Offset, ticks_offset, Ticks, raw, raw + 7);
provider!(Alternating, ticks_alternating, Ticks, raw, raw + if raw % 2 == 0 { 12 } else { 0 });
provider!(Far, ticks_far, Ticks, raw, raw + 100);
provider!(WrongUnit, millis_wrong_unit, Millis, raw, raw * 2);
