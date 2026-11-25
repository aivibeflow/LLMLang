use std::io::{self, BufRead};
use std::ops::Range;
use std::thread;

fn checked_region(start: usize, size: usize) -> Result<Range<usize>, &'static str> {
    let end = start.checked_add(size).ok_or("overflow")?;
    if end > 7 {
        return Err("out-of-bounds");
    }
    Ok(start..end)
}

fn write_region(region: &mut [u8], increment: u8) {
    for element in region {
        *element += increment;
    }
}

fn perform(values: &mut [u8; 7], source: [usize; 4]) -> Result<(), &'static str> {
    let mut first = checked_region(source[0], source[1])?;
    let mut second = checked_region(source[2], source[3])?;
    if first.is_empty() {
        write_region(&mut values[second], 23);
        return Ok(());
    }
    if second.is_empty() {
        write_region(&mut values[first], 11);
        return Ok(());
    }
    let (mut first_increment, mut second_increment) = (11, 23);
    if first.start > second.start {
        std::mem::swap(&mut first, &mut second);
        std::mem::swap(&mut first_increment, &mut second_increment);
    }
    if first.end > second.start {
        return Err("overlap");
    }
    let boundary = second.start;
    let size = second.len();
    let (prefix, suffix) = values.split_at_mut(boundary);
    let first = &mut prefix[first];
    let second = &mut suffix[..size];
    thread::scope(|scope| {
        scope.spawn(move || write_region(first, first_increment));
        scope.spawn(move || write_region(second, second_increment));
    });
    Ok(())
}

fn main() {
    for line in io::stdin().lock().lines() {
        let line = line.unwrap();
        let input: Vec<usize> = line.split_whitespace().map(|token| token.parse().unwrap()).collect();
        let mut values = [0, 1, 2, 3, 4, 5, 6];
        let result = perform(&mut values, input.try_into().unwrap());
        print!("{}", result.err().unwrap_or("ok"));
        for value in values {
            print!(" {value}");
        }
        println!();
    }
}
