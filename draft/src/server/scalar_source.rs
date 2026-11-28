//! The braced source dialect for the executable scalar semantics.

use super::{validation, Package, Result};
use proc_macro2::Span;
use serde_json::{json, Value};
use std::borrow::Cow;
use syn::{spanned::Spanned, BinOp, Block, Expr, ExprIf, Lit, LitInt, Pat, Stmt, UnOp};

fn diagnostic(span: Span, message: impl std::fmt::Display) -> super::ServerError {
    let start = span.start();
    validation(format!(
        "scalar body line {}, column {}: {message}",
        start.line,
        start.column + 1
    ))
}

pub(super) fn lower(source: &str) -> Result<Value> {
    let syntax: Block = syn::parse_str(source).map_err(|error| diagnostic(error.span(), error))?;
    if syntax.stmts.is_empty() {
        return Err(diagnostic(
            syntax.span(),
            "expected a nonempty function body",
        ));
    }
    Ok(json!(statements(&syntax)?))
}

/// Is the callable boundary supported by checked scalar lowering?
pub(super) fn supported_signature(package: &Package, row: &Value) -> bool {
    package
        .function_signature(row)
        .and_then(llmlang_spg::FunctionSignature::into_scalar)
        .is_ok()
}

pub(super) fn body<'a>(package: &Package, row: &'a Value) -> Result<Cow<'a, Value>> {
    let source = &row["canonical_body"];
    if supported_signature(package, row) {
        let text = source
            .as_str()
            .ok_or_else(|| validation("expected function source"))?;
        return lower(text).map(Cow::Owned);
    }
    Ok(Cow::Borrowed(source))
}

/// Normalize the structured Change Set shorthand to the source stored in SPG.
pub(super) fn render(value: &Value) -> Result<String> {
    fn expr(value: &Value) -> Result<String> {
        match value.as_array().map(Vec::as_slice) {
            Some([tag, literal])
                if tag == "i64" && literal.is_i64() || tag == "bool" && literal.is_boolean() =>
            {
                Ok(literal.to_string())
            }
            Some([tag, value]) if tag == "u64" && value.is_u64() => Ok(format!("{value}u64")),
            Some([tag, name]) if tag == "var" => {
                let name = name
                    .as_str()
                    .ok_or_else(|| validation("missing local name"))?;
                syn::parse_str::<syn::Ident>(name).map_err(validation)?;
                Ok(name.to_owned())
            }
            Some([tag, op, left, right])
                if tag == "bin"
                    && matches!(
                        op.as_str(),
                        Some("+" | "-" | "*" | "/" | "==" | "!=" | "<" | "<=" | ">" | ">=")
                    ) =>
            {
                Ok(format!(
                    "({} {} {})",
                    expr(left)?,
                    op.as_str().unwrap(),
                    expr(right)?
                ))
            }
            _ if value.is_object() => {
                let callee = value["callee_impl_hash"]
                    .as_str()
                    .ok_or_else(|| validation("missing callee identity"))?;
                let contract = value["required_contract_hash"]
                    .as_str()
                    .ok_or_else(|| validation("missing required contract identity"))?;
                let arguments = value["arguments"]
                    .as_array()
                    .ok_or_else(|| validation("missing call arguments"))?
                    .iter()
                    .map(expr)
                    .collect::<Result<Vec<_>>>()?;
                let suffix = if arguments.is_empty() {
                    String::new()
                } else {
                    format!(", {}", arguments.join(", "))
                };
                Ok(format!("call({callee:?}, {contract:?}{suffix})"))
            }
            _ => Err(validation("invalid scalar expression")),
        }
    }
    fn block(value: &Value, allow_empty: bool) -> Result<String> {
        let items = value
            .as_array()
            .filter(|items| allow_empty || !items.is_empty())
            .ok_or_else(|| validation("expected a nonempty scalar body"))?;
        let mut statements = Vec::new();
        for item in items {
            let statement = match item.as_array().map(Vec::as_slice) {
                Some([tag, name, value]) if tag == "let" => {
                    let name = expr(&json!(["var", name]))?;
                    format!("let {name} = {};", expr(value)?)
                }
                Some([tag, value]) if tag == "return" => format!("return {};", expr(value)?),
                Some([tag, name]) if tag == "fail" => {
                    let name = name
                        .as_str()
                        .ok_or_else(|| validation("missing error label"))?;
                    format!("return builtin__fail({name:?});")
                }
                Some([tag, condition, yes, no]) if tag == "if" => {
                    let tail = if no.as_array().is_some_and(Vec::is_empty) {
                        String::new()
                    } else {
                        format!(" else {}", block(no, false)?)
                    };
                    format!("if {} {}{tail}", expr(condition)?, block(yes, false)?)
                }
                _ => return Err(validation("invalid scalar statement")),
            };
            statements.push(statement);
        }
        Ok(format!("{{ {} }}", statements.join(" ")))
    }
    block(value, false)
}

fn statements(block: &Block) -> Result<Vec<Value>> {
    block.stmts.iter().map(statement).collect()
}

fn statement(stmt: &Stmt) -> Result<Value> {
    match stmt {
        Stmt::Local(local) if local.attrs.is_empty() => {
            let Pat::Ident(name) = &local.pat else {
                return Err(diagnostic(
                    local.pat.span(),
                    "expected an immutable local name",
                ));
            };
            if name.by_ref.is_some()
                || name.mutability.is_some()
                || name.subpat.is_some()
                || name.ident.to_string().starts_with("r#")
            {
                return Err(diagnostic(
                    name.span(),
                    "expected a plain immutable local name",
                ));
            }
            let init = local
                .init
                .as_ref()
                .filter(|init| init.diverge.is_none())
                .ok_or_else(|| diagnostic(local.span(), "expected one local initializer"))?;
            Ok(json!([
                "let",
                name.ident.to_string(),
                expression(&init.expr)?
            ]))
        }
        Stmt::Expr(Expr::Return(value), Some(_)) if value.attrs.is_empty() => {
            let value = value
                .expr
                .as_ref()
                .ok_or_else(|| diagnostic(value.span(), "return requires a value"))?;
            if let Expr::Call(call) = value.as_ref() {
                if matches!(call.func.as_ref(), Expr::Path(path) if path.path.is_ident("builtin__fail"))
                {
                    if let Some(Expr::Lit(syn::ExprLit {
                        lit: Lit::Str(label),
                        ..
                    })) = call.args.first()
                    {
                        if call.args.len() == 1 {
                            return Ok(json!(["fail", label.value()]));
                        }
                    }
                    return Err(diagnostic(call.span(), "expected one literal error label"));
                }
            }
            Ok(json!(["return", expression(value)?]))
        }
        Stmt::Expr(Expr::If(branch), None) => branch_statement(branch),
        _ => Err(diagnostic(stmt.span(), "expected let, return, or if")),
    }
}

fn branch_statement(branch: &ExprIf) -> Result<Value> {
    if !branch.attrs.is_empty() || branch.then_branch.stmts.is_empty() {
        return Err(diagnostic(
            branch.span(),
            "expected a plain if with a nonempty then block",
        ));
    }
    let otherwise = match branch.else_branch.as_ref().map(|(_, body)| body.as_ref()) {
        None => Vec::new(),
        Some(Expr::If(nested)) => vec![branch_statement(nested)?],
        Some(Expr::Block(body)) if body.attrs.is_empty() && body.label.is_none() => {
            statements(&body.block)?
        }
        Some(body) => return Err(diagnostic(body.span(), "expected else block")),
    };
    Ok(json!([
        "if",
        expression(&branch.cond)?,
        statements(&branch.then_branch)?,
        otherwise
    ]))
}

fn integer(lit: &LitInt, negated: bool) -> Result<Value> {
    let spelling = lit.to_string();
    let digits = spelling.strip_suffix(lit.suffix()).unwrap();
    if !matches!(lit.suffix(), "" | "u64")
        || !digits
            .bytes()
            .all(|byte| byte.is_ascii_digit() || byte == b'_')
    {
        return Err(diagnostic(
            lit.span(),
            "expected a decimal integer with an optional u64 suffix",
        ));
    }
    if lit.suffix() == "u64" {
        if negated {
            return Err(diagnostic(
                lit.span(),
                "unsigned integer cannot be negative",
            ));
        }
        return lit
            .base10_parse::<u64>()
            .map(|value| json!(["u64", value]))
            .map_err(|_| diagnostic(lit.span(), "integer literal out of unsigned 64-bit range"));
    }
    let value = lit
        .base10_parse::<i128>()
        .ok()
        .and_then(|n| i64::try_from(if negated { -n } else { n }).ok())
        .ok_or_else(|| diagnostic(lit.span(), "integer literal out of signed 64-bit range"))?;
    Ok(json!(["i64", value]))
}

fn expression(expr: &Expr) -> Result<Value> {
    match expr {
        Expr::Lit(literal) if literal.attrs.is_empty() => match &literal.lit {
            Lit::Int(lit) => integer(lit, false),
            Lit::Bool(lit) => Ok(json!(["bool", lit.value])),
            _ => Err(diagnostic(expr.span(), "expected a scalar literal")),
        },
        Expr::Unary(unary) if unary.attrs.is_empty() && matches!(unary.op, UnOp::Neg(_)) => {
            if let Expr::Lit(literal) = unary.expr.as_ref() {
                if let Lit::Int(lit) = &literal.lit {
                    if literal.attrs.is_empty() {
                        return integer(lit, true);
                    }
                }
            }
            Err(diagnostic(
                expr.span(),
                "unary minus requires an integer literal",
            ))
        }
        Expr::Paren(parens) if parens.attrs.is_empty() => expression(&parens.expr),
        Expr::Path(path) if path.qself.is_none() && path.attrs.is_empty() => {
            let name = path
                .path
                .get_ident()
                .map(ToString::to_string)
                .filter(|name| !name.starts_with("r#"))
                .ok_or_else(|| diagnostic(path.span(), "expected a local name"))?;
            Ok(json!(["var", name]))
        }
        Expr::Binary(binary) if binary.attrs.is_empty() => {
            let operator = match binary.op {
                BinOp::Add(_) => "+",
                BinOp::Sub(_) => "-",
                BinOp::Mul(_) => "*",
                BinOp::Div(_) => "/",
                BinOp::Eq(_) => "==",
                BinOp::Ne(_) => "!=",
                BinOp::Lt(_) => "<",
                BinOp::Le(_) => "<=",
                BinOp::Gt(_) => ">",
                BinOp::Ge(_) => ">=",
                _ => return Err(diagnostic(binary.op.span(), "unsupported scalar operator")),
            };
            Ok(json!([
                "bin",
                operator,
                expression(&binary.left)?,
                expression(&binary.right)?
            ]))
        }
        Expr::Call(call)
            if call.attrs.is_empty()
                && matches!(call.func.as_ref(), Expr::Path(path) if path.qself.is_none() && path.attrs.is_empty() && path.path.is_ident("call")) =>
        {
            let mut args = call.args.iter();
            let callee = exact_hash(args.next(), call.span(), "implementation")?;
            let required = exact_hash(args.next(), call.span(), "contract")?;
            let arguments = args.map(expression).collect::<Result<Vec<_>>>()?;
            Ok(
                json!({"callee_impl_hash": callee, "required_contract_hash": required, "arguments": arguments}),
            )
        }
        _ => Err(diagnostic(expr.span(), "unsupported scalar expression")),
    }
}

pub(super) fn exact_hash(expr: Option<&Expr>, span: Span, role: &str) -> Result<String> {
    if let Some(Expr::Lit(literal)) = expr {
        if let Lit::Str(text) = &literal.lit {
            let hash = text.value();
            let digits = hash.strip_prefix("sha256:").unwrap_or(&hash);
            if literal.attrs.is_empty()
                && digits.len() == 64
                && digits
                    .bytes()
                    .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
            {
                return Ok(hash);
            }
        }
    }
    Err(diagnostic(
        expr.map_or(span, Spanned::span),
        format!("call requires a literal {role} hash"),
    ))
}

/// Emit Rust for the same checked operations supplied to the verifier.
pub(super) fn compile(body: &Value) -> Result<Block> {
    use proc_macro2::TokenStream;
    use quote::quote;

    fn operand(value: &Value) -> Result<TokenStream> {
        if value.is_object() {
            let callee = value["callee_impl_hash"]
                .as_str()
                .ok_or_else(|| validation("missing call implementation"))?;
            let symbol = super::native::source_symbol(callee);
            let arguments = value["arguments"]
                .as_array()
                .ok_or_else(|| validation("missing call arguments"))?
                .iter()
                .map(operand)
                .collect::<Result<Vec<_>>>()?;
            return Ok(quote!(#symbol(#(#arguments),*)?));
        }
        match value.as_array().map(Vec::as_slice) {
            Some([tag, value]) if tag == "i64" => {
                let value = value
                    .as_i64()
                    .ok_or_else(|| validation("invalid integer"))?;
                Ok(quote!(#value))
            }
            Some([tag, value]) if tag == "u64" => {
                let value = value
                    .as_u64()
                    .ok_or_else(|| validation("invalid unsigned integer"))?;
                Ok(quote!(#value))
            }
            Some([tag, value]) if tag == "bool" => {
                let value = value
                    .as_bool()
                    .ok_or_else(|| validation("invalid boolean"))?;
                Ok(quote!(#value))
            }
            Some([tag, name]) if tag == "var" => {
                let name = local_name(name)?;
                Ok(quote!(#name))
            }
            Some([tag, op, left, right]) if tag == "bin" => {
                let left = operand(left)?;
                let right = operand(right)?;
                let method = match op.as_str() {
                    Some("+") => "checked_add",
                    Some("-") => "checked_sub",
                    Some("*") => "checked_mul",
                    Some("/") => {
                        return Ok(quote!({
                            let (dividend, divisor) = (#left, #right);
                            if divisor == 0 {
                                return Err(LlmlangError::DivisionByZero);
                            }
                            dividend.checked_div(divisor).ok_or(LlmlangError::ArithmeticOverflow)?
                        }));
                    }
                    Some("==" | "!=" | "<" | "<=" | ">" | ">=") => {
                        let op: TokenStream = op.as_str().unwrap().parse().map_err(validation)?;
                        return Ok(quote!((#left) #op (#right)));
                    }
                    _ => return Err(validation("unsupported scalar operator")),
                };
                let method = quote::format_ident!("{method}");
                Ok(quote!((#left).#method(#right).ok_or(LlmlangError::ArithmeticOverflow)?))
            }
            _ => Err(validation("invalid scalar operand")),
        }
    }

    fn local_name(value: &Value) -> Result<syn::Ident> {
        syn::parse_str(
            value
                .as_str()
                .ok_or_else(|| validation("missing local name"))?,
        )
        .map_err(validation)
    }

    fn statements(body: &Value) -> Result<Vec<TokenStream>> {
        body.as_array()
            .ok_or_else(|| validation("missing checked body"))?
            .iter()
            .map(|stmt| match stmt.as_array().map(Vec::as_slice) {
                Some([tag, name, value]) if tag == "let" => {
                    let name = local_name(name)?;
                    let value = operand(value)?;
                    Ok(quote!(let #name = #value;))
                }
                Some([tag, value]) if tag == "return" => {
                    let value = operand(value)?;
                    Ok(quote!(return Ok(#value);))
                }
                Some([tag, name]) if tag == "fail" => {
                    let variant = match name.as_str() {
                        Some("ArithmeticOverflow" | "DivisionByZero" | "InvalidInput") => {
                            local_name(name)?
                        }
                        _ => return Err(validation("unsupported error label")),
                    };
                    Ok(quote!(return Err(LlmlangError::#variant);))
                }
                Some([tag, condition, yes, no]) if tag == "if" => {
                    let condition = operand(condition)?;
                    let yes = statements(yes)?;
                    let no = statements(no)?;
                    Ok(quote!(if #condition { #(#yes)* } else { #(#no)* }))
                }
                _ => Err(validation("invalid checked statement")),
            })
            .collect()
    }

    let statements = statements(body)?;
    syn::parse2(quote!({ #(#statements)* })).map_err(validation)
}
