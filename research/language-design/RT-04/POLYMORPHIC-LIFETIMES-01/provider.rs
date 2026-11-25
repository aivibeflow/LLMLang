pub static STATIC_HANDLE: i32 = 7000;

pub type ScopedSelector = for<'a> fn(&'a i32, &'a i32) -> &'a i32;

pub fn select_left<'a>(left: &'a i32, _: &'a i32) -> &'a i32 {
    left
}

pub fn select_static<'a>(_: &'a i32, _: &'a i32) -> &'a i32 {
    &STATIC_HANDLE
}

pub fn static_only(left: &'static i32, _: &'static i32) -> &'static i32 {
    left
}

pub fn through<'a>(provider: ScopedSelector, left: &'a i32, right: &'a i32) -> &'a i32 {
    provider(left, right)
}

pub trait ScopedLookup {
    fn select<'a>(&self, left: &'a i32, right: &'a i32) -> &'a i32;
}

pub struct Right;
pub struct Static;

impl ScopedLookup for Right {
    fn select<'a>(&self, _: &'a i32, right: &'a i32) -> &'a i32 {
        right
    }
}

impl ScopedLookup for Static {
    fn select<'a>(&self, _: &'a i32, _: &'a i32) -> &'a i32 {
        &STATIC_HANDLE
    }
}

pub trait GenericIdentity {
    fn identity<T>(&self, value: T) -> T;
}

impl GenericIdentity for Right {
    fn identity<T>(&self, value: T) -> T {
        value
    }
}

pub trait Associated {
    type Item;
    fn item(&self) -> Self::Item;
}

impl Associated for Right {
    type Item = u16;

    fn item(&self) -> u16 {
        17
    }
}

pub trait SizedGeneric {
    fn label(&self) -> i32;
    fn map<T>(&self, value: T) -> T where Self: Sized;
}

impl SizedGeneric for Right {
    fn label(&self) -> i32 {
        19
    }

    fn map<T>(&self, value: T) -> T {
        value
    }
}
