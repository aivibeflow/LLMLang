#![forbid(unsafe_code)]

use typestate::{Ledger, Rejection, Units};

fn main() {
    let maximum = u64::MAX;
    for same_owner in [true, false] {
        for generation in [0, 7, maximum - 1, maximum] {
            for total in [0, 7, maximum - 2, maximum] {
                for revise in [false, true] {
                    for units in 0..8 {
                        let mut issuing = Ledger::new(11, generation, total);
                        let mut second = Ledger::new(12, generation, total);
                        let prepared = Units::new(units).map(|value| issuing.draft().prepare(value));
                        let target = if same_owner { &mut issuing } else { &mut second };
                        let advanced = revise && target.advance();
                        let outcome = match prepared {
                            None => "invalid-units",
                            Some(permit) => match permit.submit(target) {
                                Ok(receipt) => {
                                    assert_eq!(receipt.owner, 11);
                                    assert_eq!(receipt.parent, generation);
                                    assert_eq!(receipt.generation, target.generation());
                                    assert_eq!(receipt.units, units);
                                    "committed"
                                }
                                Err(Rejection::WrongOwner) => "wrong-owner",
                                Err(Rejection::Stale) => "stale",
                                Err(Rejection::Exhausted) => "exhausted",
                            },
                        };
                        println!("{} {} {} {}", advanced, outcome, target.generation(), target.total());
                    }
                }
            }
        }
    }

    let mut ledger = Ledger::new(11, 0, 0);
    let first = ledger.draft().prepare(Units::new(1).unwrap());
    let second = ledger.draft().prepare(Units::new(2).unwrap());
    let accepted = first.submit(&mut ledger).expect("first transition");
    assert_eq!(accepted.generation, 1);
    assert!(matches!(second.submit(&mut ledger), Err(Rejection::Stale)));
    println!("same-generation {} {}", ledger.generation(), ledger.total());
}
