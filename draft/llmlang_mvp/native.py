"""Lower the admitted scalar SPG to standalone Rust command-line programs."""

import re


RUST_TYPES = {"i64": "i64", "bool": "bool"}
CHECKED_METHODS = {"+": "checked_add", "-": "checked_sub", "*": "checked_mul"}
COMPARISONS = {"==", "!=", "<", "<=", ">", ">="}
ERRORS = {
    "InvalidInput": "invalid input",
    "DivisionByZero": "division by zero",
    "ArithmeticOverflow": "arithmetic overflow",
}
CALCULATOR_FUNCTIONS = {"+": "add", "-": "sub", "*": "mul", "/": "div"}

OUTPUT = r'''
use std::io::{self, Write};

fn write_output(data: &[u8]) -> i32 {
    let mut stdout = io::stdout().lock();
    if stdout.write_all(data).and_then(|_| stdout.flush()).is_ok() {
        0
    } else {
        1
    }
}
'''

HELLO = r'''
fn main() {
    std::process::exit(write_output(b"Hello, world!\n"));
}
'''

ECHO = r'''
use std::os::unix::ffi::OsStrExt;

fn main() {
    let mut output = Vec::new();
    for (index, argument) in std::env::args_os().skip(1).enumerate() {
        if index > 0 {
            output.push(b' ');
        }
        output.extend_from_slice(argument.as_os_str().as_bytes());
    }
    output.push(b'\n');
    std::process::exit(write_output(&output));
}
'''

CALCULATOR_HOST = r'''
use std::io::BufRead;

fn parse_i64(token: &[u8]) -> Result<i64, CalcError> {
    let (digits, negative) = match token {
        [b'-', rest @ ..] => (rest, true),
        [b'+', rest @ ..] => (rest, false),
        digits => (digits, false),
    };
    if digits.is_empty() {
        return Err(CalcError::InvalidInput);
    }
    let mut value = 0i64;
    for &byte in digits {
        if !byte.is_ascii_digit() {
            return Err(CalcError::InvalidInput);
        }
        let digit = i64::from(byte - b'0');
        value = value.checked_mul(10)
            .and_then(|prefix| {
                if negative { prefix.checked_sub(digit) } else { prefix.checked_add(digit) }
            })
            .ok_or(CalcError::InvalidInput)?;
    }
    Ok(value)
}

fn calculate() -> Result<i64, CalcError> {
    let mut record = Vec::new();
    io::stdin().lock().read_until(b'\n', &mut record)
        .map_err(|_| CalcError::InvalidInput)?;
    if record.last() == Some(&b'\n') {
        record.pop();
    }
    let mut tokens = record.split(|byte| matches!(byte, b' ' | b'\t' | b'\r'))
        .filter(|token| !token.is_empty());
    let (Some(left), Some(operation), Some(right), None) =
        (tokens.next(), tokens.next(), tokens.next(), tokens.next())
    else {
        return Err(CalcError::InvalidInput);
    };
    let left = parse_i64(left)?;
    let right = parse_i64(right)?;
'''

CALCULATOR_ENTRY = r'''
fn main() {
    let status = match calculate() {
        Ok(value) => write_output(format!("{value}\n").as_bytes()),
        Err(error) => {
            let _ = writeln!(io::stderr().lock(), "{}", error.message());
            1
        }
    };
    std::process::exit(status);
}
'''


def _local(name):
    return f"v_{name.encode('utf-8').hex()}"


def _symbol(impl_hash):
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", impl_hash):
        raise ValueError(f"invalid implementation hash: {impl_hash!r}")
    return "impl_" + impl_hash.removeprefix("sha256:")


def _expression(expr, functions):
    kind, *fields = expr
    if kind == "i64":
        return f"({fields[0]}_i64)"
    if kind == "bool":
        return "true" if fields[0] else "false"
    if kind == "var":
        return _local(fields[0])
    if kind == "call":
        callee, args, expected_hash = fields
        if callee not in functions or functions[callee]["impl_hash"] != expected_hash:
            raise ValueError(f"unresolved implementation binding: {callee} -> {expected_hash}")
        arguments = ", ".join(_expression(arg, functions) for arg in args)
        return f"{_symbol(expected_hash)}({arguments})?"
    if kind == "bin":
        operation, left, right = fields
        lhs = _expression(left, functions)
        rhs = _expression(right, functions)
        if operation in CHECKED_METHODS:
            method = CHECKED_METHODS[operation]
            return f"({lhs}).{method}({rhs}).ok_or(CalcError::ArithmeticOverflow)?"
        if operation == "/":
            return f"checked_divide({lhs}, {rhs})?"
        if operation in COMPARISONS:
            return f"({lhs} {operation} {rhs})"
    raise ValueError(f"unsupported SPG expression: {expr!r}")


def _statements(body, functions, level):
    indent = "    " * level
    for statement in body:
        kind, *fields = statement
        if kind == "let":
            name, expr = fields
            yield f"{indent}let {_local(name)} = {_expression(expr, functions)};"
        elif kind == "return":
            yield f"{indent}return Ok({_expression(fields[0], functions)});"
        elif kind == "fail":
            error, = fields
            if error not in ERRORS:
                raise ValueError(f"unsupported error: {error!r}")
            yield f"{indent}return Err(CalcError::{error});"
        elif kind == "if":
            condition, yes, no = fields
            yield f"{indent}if {_expression(condition, functions)} {{"
            yield from _statements(yes, functions, level + 1)
            if no:
                yield f"{indent}}} else {{"
                yield from _statements(no, functions, level + 1)
            yield f"{indent}}}"
        else:
            raise ValueError(f"unsupported SPG statement: {statement!r}")


def _emit_functions(functions):
    emitted = {}
    for function in functions.values():
        symbol = _symbol(function["impl_hash"])
        args = ", ".join(
            f"{_local(name)}: {RUST_TYPES[type_name]}"
            for name, type_name in function["params"]
        )
        result = RUST_TYPES[function["result"]]
        body = "\n".join(_statements(function["body"], functions, 1))
        declaration = f"fn {symbol}({args}) -> Result<{result}, CalcError> {{\n{body}\n}}"
        if symbol in emitted and emitted[symbol] != declaration:
            raise ValueError(f"different functions share an implementation identity: {symbol}")
        emitted[symbol] = declaration
    return "\n\n".join(emitted.values())


def emit_rust(spg, workload="calculator"):
    """Produce Rust for the selected CLI workload from an admitted SPG."""
    if workload == "hello":
        return OUTPUT + HELLO
    if workload == "echo":
        return OUTPUT + ECHO
    if workload != "calculator":
        raise ValueError(f"unsupported native workload: {workload!r}")
    if spg["schema"] != "llmlang-spg/v1":
        raise ValueError(f"unsupported SPG version: {spg['schema']!r}")
    functions = spg["functions"]
    dispatch = []
    for token, name in CALCULATOR_FUNCTIONS.items():
        if name not in functions:
            raise ValueError(f"Calculator is missing the public function {name!r}")
        function = functions[name]
        if [type_name for _, type_name in function["params"]] != ["i64", "i64"] or function["result"] != "i64":
            raise ValueError(f"Calculator function {name!r} requires an (i64, i64) -> i64 signature")
        dispatch.append(f'        b"{token}" => {_symbol(function["impl_hash"])}(left, right),')
    dispatch.append("        _ => Err(CalcError::InvalidInput),")
    lowerings = _emit_functions(functions)
    variants = "\n".join(f"    {error}," for error in ERRORS)
    messages = "\n".join(
        f'            Self::{error} => "{message}",' for error, message in ERRORS.items()
    )
    return f'''#![allow(dead_code, unused_parens)]
{OUTPUT}
enum CalcError {{
{variants}
}}

impl CalcError {{
    fn message(&self) -> &'static str {{
        match self {{
{messages}
        }}
    }}
}}

fn checked_divide(left: i64, right: i64) -> Result<i64, CalcError> {{
    if right == 0 {{
        return Err(CalcError::DivisionByZero);
    }}
    left.checked_div(right).ok_or(CalcError::ArithmeticOverflow)
}}

{lowerings}

{CALCULATOR_HOST}    match operation {{
{chr(10).join(dispatch)}
    }}
}}
{CALCULATOR_ENTRY}'''
