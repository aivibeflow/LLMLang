#![forbid(unsafe_code)]

pub struct Draft;
pub struct Prepared {
    units: Units,
}
pub struct Units(u8);

impl Units {
    pub fn new(amount: u8) -> Option<Self> {
        (1..=3).contains(&amount).then_some(Self(amount))
    }
}

pub struct Permit<State> {
    owner: u64,
    generation: u64,
    state: State,
}

#[derive(Debug, PartialEq, Eq)]
pub enum Rejection {
    WrongOwner,
    Stale,
    Exhausted,
}

pub struct Receipt {
    pub owner: u64,
    pub parent: u64,
    pub generation: u64,
    pub units: u8,
}

pub struct Ledger {
    owner: u64,
    generation: u64,
    total: u64,
}

impl Ledger {
    pub fn new(owner: u64, generation: u64, total: u64) -> Self {
        Self { owner, generation, total }
    }

    pub fn generation(&self) -> u64 {
        self.generation
    }

    pub fn total(&self) -> u64 {
        self.total
    }

    pub fn draft(&self) -> Permit<Draft> {
        Permit { owner: self.owner, generation: self.generation, state: Draft }
    }

    pub fn advance(&mut self) -> bool {
        if let Some(next) = self.generation.checked_add(1) {
            self.generation = next;
            true
        } else {
            false
        }
    }
}

impl Permit<Draft> {
    pub fn prepare(self, units: Units) -> Permit<Prepared> {
        Permit {
            owner: self.owner,
            generation: self.generation,
            state: Prepared { units },
        }
    }
}

impl Permit<Prepared> {
    pub fn submit(self, target: &mut Ledger) -> Result<Receipt, Rejection> {
        if self.owner != target.owner {
            return Err(Rejection::WrongOwner);
        }
        if self.generation != target.generation {
            return Err(Rejection::Stale);
        }
        let next = target.generation.checked_add(1).ok_or(Rejection::Exhausted)?;
        let units = self.state.units.0;
        let total = target.total.checked_add(u64::from(units)).ok_or(Rejection::Exhausted)?;
        target.generation = next;
        target.total = total;
        Ok(Receipt { owner: self.owner, parent: self.generation, generation: next, units })
    }
}
