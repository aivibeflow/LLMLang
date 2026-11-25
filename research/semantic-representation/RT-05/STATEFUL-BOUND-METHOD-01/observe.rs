use std::any::Any;
use std::cell::Cell;
use std::io::{self, Read};
use std::rc::Rc;

trait Method: Any {
    fn step(&self, kind: i64, input: i64) -> (i64, i64);
}

struct Bound {
    cell: Rc<Cell<i64>>,
    bias: i64,
}

impl Method for Bound {
    fn step(&self, kind: i64, input: i64) -> (i64, i64) {
        let before = self.cell.get();
        let after = match kind {
            0 => before,
            1 => before + self.bias + input,
            2 => input,
            _ => panic!("unsupported operation"),
        };
        if kind != 0 {
            self.cell.set(after);
        }
        (before, after)
    }
}

fn main() {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input).unwrap();
    let mut values = input.split_ascii_whitespace().map(|value| value.parse::<i64>().unwrap());
    while let Some(shared) = values.next() {
        let first = values.next().unwrap();
        let second = values.next().unwrap();
        let bias_left = values.next().unwrap();
        let bias_right = values.next().unwrap();
        let count = values.next().unwrap();
        assert!(shared == 0 || (shared == 1 && first == second));
        let left = Rc::new(Cell::new(first));
        let right = if shared == 1 { Rc::clone(&left) } else { Rc::new(Cell::new(second)) };
        let same_cell = Rc::ptr_eq(&left, &right);
        let receivers: [Box<dyn Method>; 2] = [
            Box::new(Bound { cell: left, bias: bias_left }),
            Box::new(Bound { cell: right, bias: bias_right }),
        ];
        let same_type = receivers[0].as_ref().type_id() == receivers[1].as_ref().type_id();
        print!("{} {}", u8::from(same_type), u8::from(same_cell));
        for _ in 0..count {
            let kind = values.next().unwrap();
            let slot = values.next().unwrap() as usize;
            let argument = values.next().unwrap();
            let (before, after) = receivers[slot].step(kind, argument);
            print!(" {before} {after}");
        }
        println!();
    }
}
