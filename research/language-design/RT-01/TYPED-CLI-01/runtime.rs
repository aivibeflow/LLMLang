use std::io::{self, BufRead, Write};
use std::os::unix::ffi::OsStrExt;

fn process_output(bytes: &[u8]) -> i32 {
    let mut output = io::stdout().lock();
    if output.write_all(bytes).and_then(|_| output.flush()).is_ok() { 0 } else { 1 }
}

fn echo(separator: &[u8], suffix: &[u8], keep_empty: bool) -> i32 {
    let mut output = Vec::new();
    let mut first = true;
    for argument in std::env::args_os().skip(1) {
        let value = argument.as_os_str().as_bytes();
        if !keep_empty && value.is_empty() {
            continue;
        }
        if !first {
            output.extend_from_slice(separator);
        }
        output.extend_from_slice(value);
        first = false;
    }
    output.extend_from_slice(suffix);
    process_output(&output)
}

#[derive(Clone, Copy)]
enum Operation { Add, Subtract, Multiply, Divide }

enum Diagnostic { Invalid, Zero, Overflow }

struct Calculator {
    separators: &'static [u8],
    terminator: u8,
    operations: &'static [(u8, Operation)],
    floor: bool,
    diagnostics_on_stdout: bool,
    diagnostics: [&'static [u8]; 3],
}

fn fail(recipe: &Calculator, reason: Diagnostic) -> i32 {
    let message = recipe.diagnostics[reason as usize];
    if recipe.diagnostics_on_stdout {
        process_output(message);
    } else {
        let mut err = io::stderr().lock();
        let _ = err.write_all(message).and_then(|_| err.flush());
    }
    1
}

fn parse_i64(data: &[u8]) -> Option<i64> {
    let ascii = std::str::from_utf8(data).ok()?;
    ascii.parse().ok()
}

fn evaluate(recipe: &Calculator, left: i64, op: u8, right: i64) -> Result<i64, Diagnostic> {
    let function = recipe.operations.iter().find(|(token, _)| *token == op).ok_or(Diagnostic::Invalid)?.1;
    let value = match function {
        Operation::Add => left.checked_add(right),
        Operation::Subtract => left.checked_sub(right),
        Operation::Multiply => left.checked_mul(right),
        Operation::Divide => {
            if right == 0 { return Err(Diagnostic::Zero); }
            let quotient = left.checked_div(right).ok_or(Diagnostic::Overflow)?;
            let rounding = recipe.floor && left % right != 0 && (left < 0) != (right < 0);
            quotient.checked_sub(i64::from(rounding))
        }
    };
    value.ok_or(Diagnostic::Overflow)
}

fn calculator(recipe: Calculator) -> i32 {
    let mut line = Vec::new();
    if io::stdin().lock().read_until(recipe.terminator, &mut line).is_err() {
        return fail(&recipe, Diagnostic::Invalid);
    }
    if line.last() == Some(&recipe.terminator) {
        line.pop();
    }
    let mut parts = line.split(|byte| recipe.separators.contains(byte)).filter(|part| !part.is_empty());
    let (Some(left), Some([op]), Some(right), None) = (parts.next(), parts.next(), parts.next(), parts.next()) else {
        return fail(&recipe, Diagnostic::Invalid);
    };
    let (Some(x), Some(y)) = (parse_i64(left), parse_i64(right)) else {
        return fail(&recipe, Diagnostic::Invalid);
    };
    match evaluate(&recipe, x, *op, y) {
        Ok(result) => process_output(format!("{result}\n").as_bytes()),
        Err(reason) => fail(&recipe, reason),
    }
}
