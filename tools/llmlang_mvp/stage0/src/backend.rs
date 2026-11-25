use std::{
    collections::{BTreeMap, BTreeSet},
    fmt::Write,
};

use serde_json::Value;

use crate::model::{error_message, valid_hash, valid_identifier, Graph, Type, ERRORS, SCHEMA};

type Bindings<'a> = BTreeMap<&'a str, Type>;

const OUTPUT: &str = include_str!("../runtime/output.rs.in");
const HELLO: &str = include_str!("../runtime/hello.rs.in");
const ECHO: &str = include_str!("../runtime/echo.rs.in");
const CALCULATOR: &str = include_str!("../runtime/calculator.rs.in");

const OPERATIONS: [(&str, &str); 4] = [("+", "add"), ("-", "sub"), ("*", "mul"), ("/", "div")];

pub fn emit(workload: &str, graph: Option<&Graph>) -> Result<String, String> {
    match workload {
        "hello" => Ok(format!("{OUTPUT}\n{HELLO}")),
        "echo" => Ok(format!("{OUTPUT}\n{ECHO}")),
        "calculator" => calculator(graph.ok_or("Calculator requires an admitted SPG")?),
        _ => Err(format!("unsupported native workload {workload:?}")),
    }
}

fn calculator(graph: &Graph) -> Result<String, String> {
    if graph.schema != SCHEMA {
        return Err(format!("unsupported SPG version {:?}", graph.schema));
    }

    let mut output = format!("#![allow(dead_code, unused_parens, unused_variables)]\n\n{OUTPUT}");
    add_errors(&mut output);

    let mut emitted = BTreeSet::new();
    for (name, function) in &graph.functions {
        if !valid_identifier(name) || !valid_hash(&function.impl_hash) {
            return Err(format!("invalid SPG implementation identity for {name:?}"));
        }
        if function
            .provided_contract_hash
            .as_deref()
            .is_some_and(|hash| !valid_hash(hash))
            || function.impl_hash != function.identity()
        {
            return Err(format!("SPG implementation digest mismatch for {name:?}"));
        }
        let mut bindings = Bindings::new();
        let mut params = Vec::new();
        for (name, typ) in &function.params {
            if !valid_identifier(name) || bindings.insert(name, *typ).is_some() {
                return Err(format!("invalid SPG parameter {name:?}"));
            }
            params.push(format!("{}: {typ}", local(name)));
        }
        let result = function.result;
        let mut body = String::new();
        let complete = statements(graph, &function.body, bindings, result, 1, &mut body)
            .map_err(|error| format!("invalid SPG function {name:?}: {error}"))?;
        if !complete {
            return Err(format!(
                "SPG function {name:?} requires an outcome on every path"
            ));
        }
        if emitted.insert(&function.impl_hash) {
            writeln!(
                output,
                "\nfn {}({}) -> Result<{result}, CalcError> {{\n{body}}}",
                symbol(&function.impl_hash),
                params.join(", ")
            )
            .unwrap();
        }
    }

    let mut dispatch = String::new();
    for (token, name) in OPERATIONS {
        let function = graph
            .functions
            .get(name)
            .ok_or_else(|| format!("Calculator is missing the public function {name:?}"))?;
        if function.params.len() != 2
            || function.params.iter().any(|(_, typ)| *typ != Type::I64)
            || function.result != Type::I64
        {
            return Err(format!(
                "Calculator function {name:?} requires an (i64, i64) -> i64 signature"
            ));
        }
        writeln!(
            dispatch,
            "        b\"{token}\" => {}(left, right),",
            symbol(&function.impl_hash)
        )
        .unwrap();
    }
    dispatch.push_str("        _ => Err(CalcError::InvalidInput),");
    output.push('\n');
    output.push_str(&CALCULATOR.replace("@DISPATCH@", &dispatch));
    Ok(output)
}

fn add_errors(output: &mut String) {
    output.push_str("\nenum CalcError {\n");
    for (name, _) in ERRORS {
        writeln!(output, "    {name},").unwrap();
    }
    output.push_str(
        "}\n\nimpl CalcError {\n    fn message(&self) -> &'static str {\n        match self {\n",
    );
    for (name, message) in ERRORS {
        writeln!(output, "            Self::{name} => {message:?},").unwrap();
    }
    output.push_str("        }\n    }\n}\n");
    output.push_str(
        r#"
fn checked_divide(left: i64, right: i64) -> Result<i64, CalcError> {
    if right == 0 {
        return Err(CalcError::DivisionByZero);
    }
    left.checked_div(right).ok_or(CalcError::ArithmeticOverflow)
}
"#,
    );
}

fn symbol(hash: &str) -> String {
    // The callers validate implementation identities before emitting them.
    format!("impl_{}", hash.trim_start_matches("sha256:"))
}

fn local(name: &str) -> String {
    let mut identifier = String::from("v_");
    for byte in name.bytes() {
        write!(identifier, "{byte:02x}").unwrap();
    }
    identifier
}

fn array(value: &Value) -> Result<&[Value], String> {
    value
        .as_array()
        .map(Vec::as_slice)
        .ok_or_else(|| "expected an SPG array".into())
}

fn text(value: &Value) -> Result<&str, String> {
    value
        .as_str()
        .ok_or_else(|| "expected an SPG string".into())
}

fn tagged(node: &Value) -> Result<(&str, &[Value]), String> {
    let (name, fields) = array(node)?.split_first().ok_or("SPG tag is missing")?;
    Ok((text(name)?, fields))
}

fn statements<'a>(
    graph: &Graph,
    body: &'a [Value],
    mut bindings: Bindings<'a>,
    result: Type,
    level: usize,
    output: &mut String,
) -> Result<bool, String> {
    let indent = "    ".repeat(level);
    let mut complete = false;
    for statement in body {
        if complete {
            return Err("unreachable SPG statement".into());
        }
        match tagged(statement)? {
            ("let", [name, value]) => {
                let name = text(name)?;
                let (expr, typ) = expression(graph, value, &bindings)?;
                if !valid_identifier(name) || bindings.insert(name, typ).is_some() {
                    return Err(format!("invalid SPG local binding {name:?}"));
                }
                writeln!(output, "{indent}let {} = {expr};", local(name)).unwrap();
            }
            ("return", [value]) => {
                let (expr, typ) = expression(graph, value, &bindings)?;
                if typ != result {
                    return Err(format!("expected return type {result}, got {typ}"));
                }
                writeln!(output, "{indent}return Ok({expr});").unwrap();
                complete = true;
            }
            ("fail", [name]) => {
                let name = text(name)?;
                if error_message(name).is_none() {
                    return Err(format!("unsupported SPG error {name:?}"));
                }
                writeln!(output, "{indent}return Err(CalcError::{name});").unwrap();
                complete = true;
            }
            ("if", [value, yes, no]) => {
                let (condition, typ) = expression(graph, value, &bindings)?;
                if typ != Type::Bool {
                    return Err("SPG if condition must have type bool".into());
                }
                let (yes, no) = (array(yes)?, array(no)?);
                if yes.is_empty() {
                    return Err("SPG then branch cannot be empty".into());
                }
                writeln!(output, "{indent}if {condition} {{").unwrap();
                let then_complete =
                    statements(graph, yes, bindings.clone(), result, level + 1, output)?;
                let else_complete = if no.is_empty() {
                    false
                } else {
                    writeln!(output, "{indent}}} else {{").unwrap();
                    statements(graph, no, bindings.clone(), result, level + 1, output)?
                };
                writeln!(output, "{indent}}}").unwrap();
                complete = then_complete && else_complete;
            }
            (tag, _) => return Err(format!("unsupported SPG statement {tag:?}")),
        }
    }
    Ok(complete)
}

fn expression(
    graph: &Graph,
    value: &Value,
    bindings: &Bindings<'_>,
) -> Result<(String, Type), String> {
    match tagged(value)? {
        ("i64", [integer]) => {
            let integer = integer
                .as_i64()
                .ok_or("SPG integer out of signed 64-bit range")?;
            Ok((format!("({integer}_i64)"), Type::I64))
        }
        ("bool", [boolean]) => {
            let boolean = boolean.as_bool().ok_or("expected a Boolean SPG literal")?;
            Ok((boolean.to_string(), Type::Bool))
        }
        ("var", [name]) => {
            let name = text(name)?;
            let typ = bindings
                .get(name)
                .ok_or_else(|| format!("unknown SPG variable {name:?}"))?;
            Ok((local(name), *typ))
        }
        ("bin", [op, left, right]) => {
            let (lhs, lhs_type) = expression(graph, left, bindings)?;
            let (rhs, rhs_type) = expression(graph, right, bindings)?;
            let op = text(op)?;
            match op {
                "+" | "-" | "*" | "/" if lhs_type == Type::I64 && rhs_type == Type::I64 => {
                    let method = match op {
                        "+" => "checked_add",
                        "-" => "checked_sub",
                        "*" => "checked_mul",
                        "/" => return Ok((format!("checked_divide({lhs}, {rhs})?"), Type::I64)),
                        _ => unreachable!(),
                    };
                    Ok((
                        format!("({lhs}).{method}({rhs}).ok_or(CalcError::ArithmeticOverflow)?"),
                        Type::I64,
                    ))
                }
                "==" | "!=" if lhs_type == rhs_type => {
                    Ok((format!("({lhs} {op} {rhs})"), Type::Bool))
                }
                "<" | "<=" | ">" | ">=" if lhs_type == Type::I64 && rhs_type == Type::I64 => {
                    Ok((format!("({lhs} {op} {rhs})"), Type::Bool))
                }
                _ => Err(format!(
                    "unsupported SPG operator {op:?} for {lhs_type} and {rhs_type}"
                )),
            }
        }
        ("call", [name, args, hash]) => {
            let (name, hash) = (text(name)?, text(hash)?);
            let callee = graph
                .functions
                .get(name)
                .filter(|callee| callee.impl_hash == hash && valid_hash(hash))
                .ok_or_else(|| format!("unresolved implementation binding: {name} -> {hash}"))?;
            let args = array(args)?;
            if args.len() != callee.params.len() {
                return Err(format!("argument count mismatch in call to {name:?}"));
            }
            let mut arguments = Vec::new();
            for (arg, (_, expected)) in args.iter().zip(&callee.params) {
                let (expr, actual) = expression(graph, arg, bindings)?;
                if actual != *expected {
                    return Err(format!("expected argument type {expected}, got {actual}"));
                }
                arguments.push(expr);
            }
            Ok((
                format!("{}({})?", symbol(hash), arguments.join(", ")),
                callee.result,
            ))
        }
        (tag, _) => Err(format!("unsupported SPG expression {tag:?}")),
    }
}
