use std::{
    borrow::Cow,
    collections::{BTreeMap, BTreeSet},
};

use rustpython_parser::{
    ast::{self, CmpOp, Constant, Expr, Operator, Ranged, Stmt, StmtFunctionDef, UnaryOp},
    text_size::TextSize,
    Parse,
};
use serde_json::{json, Value};
use unicode_normalization::UnicodeNormalization;

use crate::model::{
    error_message, valid_hash, valid_identifier, Function, Graph, Signature, Type, SCHEMA,
};

type Bindings = BTreeMap<String, Type>;

pub fn lower(
    source: &str,
    path: &str,
    contracts: Option<BTreeMap<String, String>>,
) -> Result<Graph, String> {
    let source = source.replace("\r\n", "\n").replace('\r', "\n");
    let module = ast::Suite::parse(&source, path)
        .map_err(|error| diagnostic(&source, error.offset, error.error))?;
    let mut nodes = BTreeMap::new();
    for statement in &module {
        let Stmt::FunctionDef(node) = statement else {
            return Err(at(
                &source,
                statement,
                "only function declarations are supported at module scope",
            ));
        };
        let name = identifier(&source, node, node.name.as_str())?;
        if nodes.insert(name.clone(), node).is_some() {
            return Err(at(&source, node, format!("duplicate function {name:?}")));
        }
    }
    if nodes.is_empty() {
        return Err("expected at least one function declaration".into());
    }

    if let Some(hashes) = &contracts {
        if !hashes
            .keys()
            .map(String::as_str)
            .eq(nodes.keys().map(String::as_str))
        {
            return Err("provided contract hashes must name exactly the declared functions".into());
        }
        if hashes.values().any(|hash| !valid_hash(hash)) {
            return Err("invalid provided contract hash".into());
        }
    }

    let signatures = nodes
        .iter()
        .map(|(name, node)| Ok((name.as_str(), signature(&source, node)?)))
        .collect::<Result<BTreeMap<_, _>, String>>()?;
    let mut lowerer = Lowerer {
        source: &source,
        nodes: &nodes,
        signatures,
        contracts: contracts.unwrap_or_default(),
        active: BTreeSet::new(),
        functions: BTreeMap::new(),
    };
    for (name, node) in &nodes {
        lowerer.lower_function(name, *node)?;
    }
    Ok(Graph {
        schema: SCHEMA.into(),
        functions: lowerer.functions,
    })
}

fn diagnostic(source: &str, offset: TextSize, message: impl std::fmt::Display) -> String {
    let prefix = &source.as_bytes()[..usize::from(offset).min(source.len())];
    let line = 1 + prefix.iter().filter(|&&byte| byte == b'\n').count();
    let column = prefix
        .iter()
        .rev()
        .take_while(|&&byte| byte != b'\n')
        .count()
        + 1;
    format!("line {line}, column {column}: {message}")
}

fn at(source: &str, node: &impl Ranged, message: impl std::fmt::Display) -> String {
    diagnostic(source, node.range().start(), message)
}

fn normalized(name: &str) -> Cow<'_, str> {
    if name.is_ascii() {
        Cow::Borrowed(name)
    } else {
        Cow::Owned(name.nfkc().collect())
    }
}

fn identifier(source: &str, node: &impl Ranged, name: &str) -> Result<String, String> {
    let canonical = normalized(name);
    if valid_identifier(&canonical) {
        Ok(canonical.into_owned())
    } else {
        Err(at(source, node, format!("unsupported identifier {name:?}")))
    }
}

fn source_type(
    source: &str,
    node: &impl Ranged,
    annotation: Option<&Expr>,
) -> Result<Type, String> {
    if let Some(Expr::Name(name)) = annotation {
        match normalized(name.id.as_str()).as_ref() {
            "int" => return Ok(Type::I64),
            "bool" => return Ok(Type::Bool),
            _ => {}
        }
    }
    let offset = annotation.map_or(node.range(), Ranged::range).start();
    Err(diagnostic(
        source,
        offset,
        "type annotation must be int or bool",
    ))
}

fn signature(source: &str, node: &StmtFunctionDef) -> Result<Signature, String> {
    let args = &node.args;
    if !node.decorator_list.is_empty()
        || !node.type_params.is_empty()
        || !args.posonlyargs.is_empty()
        || !args.kwonlyargs.is_empty()
        || args.vararg.is_some()
        || args.kwarg.is_some()
        || args.args.iter().any(|argument| argument.default.is_some())
    {
        return Err(at(
            source,
            node,
            "only plain functions with named typed parameters are supported",
        ));
    }
    let mut params = Vec::new();
    let mut names = BTreeSet::new();
    for argument in &args.args {
        let argument = &argument.def;
        let name = identifier(source, argument, argument.arg.as_str())?;
        if !names.insert(name.clone()) {
            return Err(at(source, node, format!("duplicate parameter {name:?}")));
        }
        let typ = source_type(source, argument, argument.annotation.as_deref())?;
        params.push((name, typ));
    }
    Ok(Signature {
        params,
        result: source_type(source, node, node.returns.as_deref())?,
    })
}

struct Lowerer<'a> {
    source: &'a str,
    nodes: &'a BTreeMap<String, &'a StmtFunctionDef>,
    signatures: BTreeMap<&'a str, Signature>,
    contracts: BTreeMap<String, String>,
    active: BTreeSet<String>,
    functions: BTreeMap<String, Function>,
}

impl Lowerer<'_> {
    fn lower_function(&mut self, name: &str, reference: &impl Ranged) -> Result<&str, String> {
        if !self.functions.contains_key(name) {
            if !self.active.insert(name.to_owned()) {
                return Err(at(
                    self.source,
                    reference,
                    format!("recursive call to {name:?} is outside the scalar profile"),
                ));
            }
            let node = self.nodes[name];
            let Signature { params, result } = self.signatures[name].clone();
            let bindings = params.iter().cloned().collect();
            let (body, complete) = self.block(&node.body, bindings, result)?;
            if !complete {
                return Err(at(
                    self.source,
                    node,
                    format!("function {name:?} must return or fail on every path"),
                ));
            }
            let mut function = Function {
                params,
                result,
                body,
                provided_contract_hash: self.contracts.get(name).cloned(),
                impl_hash: String::new(),
            };
            function.impl_hash = function.identity();
            self.functions.insert(name.to_owned(), function);
            self.active.remove(name);
        }
        Ok(&self.functions[name].impl_hash)
    }

    fn block(
        &mut self,
        statements: &[Stmt],
        mut bindings: Bindings,
        result: Type,
    ) -> Result<(Vec<Value>, bool), String> {
        let mut body = Vec::new();
        let mut complete = false;
        for statement in statements {
            if complete {
                return Err(at(self.source, statement, "unreachable statement"));
            }
            let lowered = match statement {
                Stmt::Assign(assign) => {
                    let [Expr::Name(target)] = assign.targets.as_slice() else {
                        return Err(at(
                            self.source,
                            statement,
                            "only a single local name can be assigned",
                        ));
                    };
                    let name = identifier(self.source, statement, target.id.as_str())?;
                    if bindings.contains_key(&name) {
                        return Err(at(
                            self.source,
                            statement,
                            format!("binding {name:?} already exists"),
                        ));
                    }
                    let (expr, typ) = self.expression(&assign.value, &bindings)?;
                    let statement = json!(["let", name, expr]);
                    bindings.insert(name, typ);
                    statement
                }
                Stmt::If(branch) => {
                    let (condition, typ) = self.expression(&branch.test, &bindings)?;
                    if typ != Type::Bool {
                        return Err(at(
                            self.source,
                            branch.test.as_ref(),
                            "if condition must have type bool",
                        ));
                    }
                    let (yes, then_complete) =
                        self.block(&branch.body, bindings.clone(), result)?;
                    let (no, else_complete) =
                        self.block(&branch.orelse, bindings.clone(), result)?;
                    complete = then_complete && else_complete;
                    json!(["if", condition, yes, no])
                }
                Stmt::Return(ret) => {
                    let value = ret
                        .value
                        .as_deref()
                        .ok_or_else(|| at(self.source, statement, "return requires a value"))?;
                    complete = true;
                    if let Some(call) = failure_call(value) {
                        failure(self.source, call)?
                    } else {
                        let (expr, typ) = self.expression(value, &bindings)?;
                        if typ != result {
                            return Err(at(
                                self.source,
                                value,
                                format!("expected return type {result}, got {typ}"),
                            ));
                        }
                        json!(["return", expr])
                    }
                }
                Stmt::Expr(expr) if failure_call(&expr.value).is_some() => {
                    complete = true;
                    failure(self.source, failure_call(&expr.value).unwrap())?
                }
                _ => {
                    return Err(at(
                        self.source,
                        statement,
                        "unsupported statement in scalar profile",
                    ))
                }
            };
            body.push(lowered);
        }
        Ok((body, complete))
    }

    fn expression(&mut self, node: &Expr, bindings: &Bindings) -> Result<(Value, Type), String> {
        match node {
            Expr::Constant(constant) => match &constant.value {
                Constant::Bool(value) => Ok((json!(["bool", value]), Type::Bool)),
                Constant::Int(value) => integer(self.source, node, i64::try_from(value)),
                _ => Err(at(
                    self.source,
                    node,
                    "unsupported literal in scalar profile",
                )),
            },
            Expr::UnaryOp(expr) if expr.op == UnaryOp::USub => {
                if let Expr::Constant(constant) = expr.operand.as_ref() {
                    if let Constant::Int(value) = &constant.value {
                        return integer(self.source, node, i64::try_from(-value));
                    }
                }
                Err(at(
                    self.source,
                    node,
                    "unary minus requires an integer literal",
                ))
            }
            Expr::Name(variable) => {
                let canonical = normalized(variable.id.as_str());
                let name = canonical.as_ref();
                let typ = bindings
                    .get(name)
                    .ok_or_else(|| at(self.source, node, format!("unknown variable {name:?}")))?;
                Ok((json!(["var", name]), *typ))
            }
            Expr::BinOp(expr) => {
                let op = match expr.op {
                    Operator::Add => "+",
                    Operator::Sub => "-",
                    Operator::Mult => "*",
                    Operator::Div => "/",
                    _ => return Err(at(self.source, node, "unsupported arithmetic operator")),
                };
                let (left, lhs) = self.expression(&expr.left, bindings)?;
                let (right, rhs) = self.expression(&expr.right, bindings)?;
                if lhs != Type::I64 || rhs != Type::I64 {
                    return Err(at(
                        self.source,
                        node,
                        "arithmetic operands must have type i64",
                    ));
                }
                Ok((json!(["bin", op, left, right]), Type::I64))
            }
            Expr::Compare(expr) => {
                let ([operator], [comparator]) = (expr.ops.as_slice(), expr.comparators.as_slice())
                else {
                    return Err(at(
                        self.source,
                        node,
                        "chained comparisons are outside the scalar profile",
                    ));
                };
                let op = match operator {
                    CmpOp::Eq => "==",
                    CmpOp::NotEq => "!=",
                    CmpOp::Lt => "<",
                    CmpOp::LtE => "<=",
                    CmpOp::Gt => ">",
                    CmpOp::GtE => ">=",
                    _ => return Err(at(self.source, node, "unsupported comparison operator")),
                };
                let (left, lhs) = self.expression(&expr.left, bindings)?;
                let (right, rhs) = self.expression(comparator, bindings)?;
                if lhs != rhs || (lhs != Type::I64 && !matches!(operator, CmpOp::Eq | CmpOp::NotEq))
                {
                    return Err(at(self.source, node, "incompatible comparison operands"));
                }
                Ok((json!(["bin", op, left, right]), Type::Bool))
            }
            Expr::Call(call) if call.keywords.is_empty() => {
                let Expr::Name(callee) = call.func.as_ref() else {
                    return Err(at(
                        self.source,
                        node,
                        "only direct calls to declared functions are supported",
                    ));
                };
                let canonical = normalized(callee.id.as_str());
                let name = canonical.as_ref();
                let signature =
                    self.signatures.get(name).cloned().ok_or_else(|| {
                        at(self.source, node, format!("unknown function {name:?}"))
                    })?;
                if call.args.len() != signature.params.len() {
                    return Err(at(
                        self.source,
                        node,
                        format!("argument count mismatch in call to {name:?}"),
                    ));
                }
                let mut args = Vec::new();
                for (argument, (_, expected)) in call.args.iter().zip(signature.params) {
                    let (expr, actual) = self.expression(argument, bindings)?;
                    if actual != expected {
                        return Err(at(
                            self.source,
                            argument,
                            format!("expected argument type {expected}, got {actual}"),
                        ));
                    }
                    args.push(expr);
                }
                let hash = self.lower_function(name, node)?;
                Ok((json!(["call", name, args, hash]), signature.result))
            }
            _ => Err(at(
                self.source,
                node,
                "unsupported expression in scalar profile",
            )),
        }
    }
}

fn integer<E>(source: &str, node: &Expr, value: Result<i64, E>) -> Result<(Value, Type), String> {
    let value =
        value.map_err(|_| at(source, node, "integer literal out of signed 64-bit range"))?;
    Ok((json!(["i64", value]), Type::I64))
}

fn failure_call(value: &Expr) -> Option<&ast::ExprCall> {
    if let Expr::Call(call) = value {
        if matches!(call.func.as_ref(), Expr::Name(name) if normalized(name.id.as_str()) == "fail")
        {
            return Some(call);
        }
    }
    None
}

fn failure(source: &str, call: &ast::ExprCall) -> Result<Value, String> {
    if call.keywords.is_empty() {
        if let [Expr::Constant(argument)] = call.args.as_slice() {
            if let Constant::Str(name) = &argument.value {
                if error_message(name).is_some() {
                    return Ok(json!(["fail", name]));
                }
            }
        }
    }
    Err(at(
        source,
        call,
        "fail requires a supported literal error name",
    ))
}
