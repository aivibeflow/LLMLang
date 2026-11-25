use std::cell::{Cell, RefCell};
use std::io::{self, BufRead};

struct Context {
    cell: Cell<u32>,
    trace: RefCell<Vec<u32>>,
}

fn operand(ctx: &Context, stage: u32, behavior: u32) -> Result<u32, u32> {
    let before = ctx.cell.get();
    if behavior == 1 || behavior == 2 {
        ctx.cell.set(before ^ 1);
    }
    let after = ctx.cell.get();
    ctx.trace.borrow_mut().push(4 * stage + 2 * before + after);
    if behavior >= 2 {
        Err(stage)
    } else {
        Ok(after)
    }
}

fn body(ctx: &Context, left: u32, right: u32) -> u32 {
    operand(ctx, 3, 0).expect("body marker has no failure");
    2 * left + right
}

type Callee = fn(&Context, u32, u32) -> u32;

fn target(ctx: &Context, behavior: u32) -> Result<Callee, u32> {
    operand(ctx, 0, behavior)?;
    Ok(body)
}

fn run(ctx: &Context, receiver: u32, left: u32, right: u32) -> Result<u32, u32> {
    Ok(target(ctx, receiver)?(ctx, operand(ctx, 1, left)?, operand(ctx, 2, right)?))
}

fn main() {
    for line in io::stdin().lock().lines() {
        let line = line.expect("fixture input");
        let mut fields = line.split_whitespace().map(|n| n.parse::<u32>().expect("unsigned input"));
        let initial = fields.next().expect("initial cell");
        let receiver = fields.next().expect("receiver behavior");
        let left = fields.next().expect("left behavior");
        let right = fields.next().expect("right behavior");
        let ctx = Context { cell: Cell::new(initial), trace: RefCell::new(Vec::new()) };
        match run(&ctx, receiver, left, right) {
            Ok(result) => print!("return {result}"),
            Err(stage) => print!("error {stage}"),
        }
        print!(" {}", ctx.cell.get());
        for event in ctx.trace.into_inner() {
            print!(" {event}");
        }
        println!();
    }
}
