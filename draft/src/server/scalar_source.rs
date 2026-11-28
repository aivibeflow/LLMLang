//! The braced source dialect for the executable scalar semantics.

use super::{validation, Package, Result};
use proc_macro2::Span;
use serde_json::{json, Value};
use std::borrow::Cow;
use syn::{spanned::Spanned, BinOp, Block, Expr, ExprIf, Lit, LitInt, Pat, Stmt, UnOp};

pub(super) const PROFILE: &str = "scalar-v1";

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

pub(super) fn body<'a>(package: &Package, row: &'a Value) -> Result<Cow<'a, Value>> {
    let source = &row["canonical_body"];
    if let Some(text) = source.as_str() {
        let profile = row["provided_contract_hash"]
            .as_str()
            .and_then(|id| package.tables["contracts"].get(id))
            .and_then(|row| row["profile"].as_str());
        if profile.map_or_else(
            || !super::native::is_native(&package.tables),
            |profile| profile == PROFILE,
        ) {
            return lower(text).map(Cow::Owned);
        }
    }
    Ok(Cow::Borrowed(source))
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
    if !lit.suffix().is_empty()
        || !lit
            .to_string()
            .bytes()
            .all(|byte| byte.is_ascii_digit() || byte == b'_')
    {
        return Err(diagnostic(
            lit.span(),
            "expected a decimal integer without a suffix",
        ));
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

fn exact_hash(expr: Option<&Expr>, span: Span, role: &str) -> Result<String> {
    if let Some(Expr::Lit(literal)) = expr {
        if let Lit::Str(text) = &literal.lit {
            let hash = text.value();
            if literal.attrs.is_empty()
                && hash.len() == 64
                && hash
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
