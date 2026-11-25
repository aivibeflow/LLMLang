#[derive(Debug)]
enum Refusal {
    OutOfBounds,
    Overlap,
}

fn set_pair(first: &mut u8, second: &mut u8) {
    *first = 91;
    *second = 92;
}

fn two_mut(data: &mut [u8], first: usize, second: usize) -> Result<(&mut u8, &mut u8), Refusal> {
    if first >= data.len() || second >= data.len() {
        return Err(Refusal::OutOfBounds);
    }
    match first.cmp(&second) {
        std::cmp::Ordering::Less => {
            let (before, after) = data.split_at_mut(second);
            Ok((&mut before[first], &mut after[0]))
        }
        std::cmp::Ordering::Greater => {
            let (before, after) = data.split_at_mut(first);
            Ok((&mut after[0], &mut before[second]))
        }
        std::cmp::Ordering::Equal => Err(Refusal::Overlap),
    }
}

#[cfg(not(any(raw_indices, escaped_borrow)))]
fn main() {
    let mut fields = (10u8, 20u8);
    set_pair(&mut fields.0, &mut fields.1);
    assert_eq!(fields, (91, 92));

    let values = [10, 20, 30, 40];
    for length in 0..=values.len() {
        for first in 0..=5 {
            for second in 0..=5 {
                let mut data = values;
                let slice = &mut data[..length];
                let disposition = match two_mut(slice, first, second) {
                    Ok((one, two)) => {
                        set_pair(one, two);
                        "paired"
                    }
                    Err(Refusal::OutOfBounds) => "out-of-bounds",
                    Err(Refusal::Overlap) => "overlap",
                };
                let text = slice.iter().map(u8::to_string).collect::<Vec<_>>().join(",");
                println!("{length}:{first}:{second}:{disposition}:{text}");
            }
        }
    }
}

#[cfg(raw_indices)]
fn main() {
    let mut data = [10, 20];
    set_pair(&mut data[0], &mut data[1]);
}

#[cfg(escaped_borrow)]
fn main() {
    let pair = {
        let mut data = [10, 20];
        two_mut(&mut data, 0, 1).unwrap()
    };
    set_pair(pair.0, pair.1);
}
