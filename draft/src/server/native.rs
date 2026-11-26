//! Lower the native Linux x86-64 profile to a temporary Rust translation unit.

use super::{invalid, validation, Package, Path, Result, ServerError};
use quote::{format_ident, quote, ToTokens};
use serde_json::{json, Value};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    process::Command,
};
use syn::{
    parse_quote,
    visit_mut::{self, VisitMut},
    Expr, Item, Type,
};

const PROFILE: &str = "linux-x86_64-native-v1";

pub(super) fn is_native(package: &Package) -> bool {
    !package.tables["contracts"].is_empty()
        && package.tables["contracts"]
            .values()
            .all(|row| row["profile"] == PROFILE)
}

#[derive(Clone)]
struct Call {
    name: String,
    number: u16,
    types: Vec<String>,
}

fn native_call(row: &Value) -> Result<Call> {
    let source = row["canonical_body"]
        .as_str()
        .ok_or_else(|| invalid("expected native syscall source"))?;
    let (head, body) = source
        .split_once('{')
        .ok_or_else(|| invalid("native syscall has no body"))?;
    let head = head
        .strip_prefix("unsafe fn ")
        .ok_or_else(|| invalid("expected directly callable unsafe syscall"))?;
    let (name, params) = head
        .split_once('(')
        .ok_or_else(|| invalid("missing native parameters"))?;
    let (params, result) = params
        .split_once(')')
        .ok_or_else(|| invalid("missing native result"))?;
    if !identifier(name) || result.trim() != "-> AbiResult" {
        return Err(invalid("unsupported native syscall declaration"));
    }
    let (mut names, mut types) = (Vec::new(), Vec::new());
    let expected = row["typed_signature"]["parameters"]
        .as_array()
        .ok_or_else(|| invalid("missing native signature"))?;
    for parameter in params.split(',').filter(|part| !part.trim().is_empty()) {
        let (param, kind) = parameter
            .split_once(':')
            .ok_or_else(|| invalid("invalid native parameter"))?;
        let (param, kind) = (param.trim(), kind.trim());
        let declared = expected
            .get(names.len())
            .ok_or_else(|| invalid("native signature arity mismatch"))?;
        if !identifier(param)
            || names.contains(&param)
            || declared["name"] != param
            || declared["type"] != kind
        {
            return Err(invalid(format!(
                "native signature disagrees with source for {name}"
            )));
        }
        names.push(param);
        types.push(kind.to_owned());
    }
    if names.len() != expected.len()
        || names.len() > 6
        || row["typed_signature"]["result"] != "AbiResult"
    {
        return Err(invalid("unsupported syscall signature"));
    }
    let args = body
        .trim()
        .strip_suffix('}')
        .and_then(|body| body.trim().strip_prefix("syscall("))
        .and_then(|body| body.strip_suffix(')'))
        .ok_or_else(|| invalid("expected a single syscall invocation"))?;
    let mut args = args.split(',').map(str::trim);
    let number = args
        .next()
        .and_then(|number| number.parse().ok())
        .ok_or_else(|| invalid("invalid syscall number"))?;
    if args.ne(names) {
        return Err(invalid(format!(
            "{name}: syscall operands disagree with signature"
        )));
    }
    Ok(Call {
        name: name.into(),
        number,
        types,
    })
}

fn identifier(name: &str) -> bool {
    let mut bytes = name.bytes();
    bytes
        .next()
        .is_some_and(|byte| byte.is_ascii_alphabetic() || byte == b'_')
        && bytes.all(|byte| byte.is_ascii_alphanumeric() || byte == b'_')
}

fn pinned_calls(
    package: &Package,
    body: &Value,
    allowed: &BTreeSet<(String, String)>,
) -> Result<BTreeMap<String, Call>> {
    let mut calls = BTreeMap::new();
    for pin in body["calls"]
        .as_array()
        .ok_or_else(|| invalid("missing native call pins"))?
    {
        let implementation = pin["callee_impl_hash"]
            .as_str()
            .ok_or_else(|| invalid("missing implementation pin"))?;
        let row = package.tables["functions"]
            .get(implementation)
            .ok_or_else(|| invalid("unresolved native implementation pin"))?;
        let contract = pin["required_contract_hash"]
            .as_str()
            .ok_or_else(|| invalid("missing native contract pin"))?;
        if row["provided_contract_hash"] != contract
            || !allowed.contains(&(implementation.to_owned(), contract.to_owned()))
        {
            return Err(invalid(
                "native call must use an implementation and contract selected by a public binding",
            ));
        }
        let call = native_call(row)?;
        if calls.insert(call.name.clone(), call).is_some() {
            return Err(invalid("ambiguous native call name"));
        }
    }
    Ok(calls)
}

struct Lower<'a> {
    calls: &'a BTreeMap<String, Call>,
    used: BTreeSet<String>,
    error: Option<ServerError>,
}

impl Lower<'_> {
    fn reject(&mut self, message: impl Into<String>) {
        if self.error.is_none() {
            self.error = Some(invalid(message));
        }
    }

    fn word(&mut self, kind: &str, arg: &Expr) -> Expr {
        if matches!(arg, Expr::Path(path) if path.path.is_ident("null")) {
            return parse_quote!(0usize);
        }
        let kind = kind
            .strip_prefix("Nullable<")
            .and_then(|s| s.strip_suffix('>'))
            .unwrap_or(kind);
        match kind {
            "U8" | "U16" | "U32" | "U64" | "Usize" | "I16" | "I32" | "I64" => {
                parse_quote!((#arg) as usize)
            }
            "CString" => {
                if matches!(arg, Expr::MethodCall(call) if call.method == "as_ptr") {
                    parse_quote!((#arg) as usize)
                } else {
                    parse_quote!((#arg).as_ptr() as usize)
                }
            }
            kind if [
                "ConstPtr<",
                "MutPtr<",
                "NulTerminatedArray<",
                "ReadBuffer<",
                "WriteBuffer<",
            ]
            .iter()
            .any(|prefix| kind.starts_with(prefix)) =>
            {
                parse_quote!((#arg) as *const _ as *const u8 as usize)
            }
            _ => {
                self.reject(format!("unsupported syscall parameter type {kind}"));
                parse_quote!(0usize)
            }
        }
    }
}

impl VisitMut for Lower<'_> {
    fn visit_attribute_mut(&mut self, _: &mut syn::Attribute) {
        self.reject("attributes are unsupported in native source");
    }
    fn visit_macro_mut(&mut self, _: &mut syn::Macro) {
        self.reject("macros are unsupported in native source");
    }
    fn visit_item_mut(&mut self, _: &mut Item) {
        self.reject("nested items are unsupported in native source");
    }

    fn visit_expr_mut(&mut self, expr: &mut Expr) {
        visit_mut::visit_expr_mut(self, expr);

        if matches!(expr, Expr::Unsafe(_) | Expr::Verbatim(_)) {
            self.reject("unsupported native source expression");
            return;
        }
        if let Expr::Array(array) = expr {
            for value in &mut array.elems {
                if matches!(value, Expr::Path(path) if path.path.is_ident("null")) {
                    *value = parse_quote!(std::ptr::null::<std::ffi::c_char>());
                } else if matches!(value, Expr::Lit(literal) if matches!(literal.lit, syn::Lit::CStr(_)))
                {
                    *value = parse_quote!((#value).as_ptr());
                }
            }
        }
        if let Expr::Cast(cast) = expr {
            if matches!(cast.ty.as_ref(), Type::Path(path) if path.path.segments.last().is_some_and(|segment| segment.ident == "MutPtr"))
            {
                let ty = &cast.ty;
                let value = &cast.expr;
                *expr = parse_quote!((#value as *mut _) as #ty);
            }
        }
        let Expr::Call(call) = expr else { return };
        let Expr::Path(ref callee) = *call.func else {
            self.reject("native source requires direct calls");
            return;
        };
        let name = callee
            .path
            .segments
            .iter()
            .map(|part| part.ident.to_string())
            .collect::<Vec<_>>()
            .join("::");
        if let Some(native) = self.calls.get(&name).cloned() {
            if call.args.len() != native.types.len() {
                self.reject(format!("{name}: wrong native argument count"));
                return;
            }
            self.used.insert(name);
            if native.name == "pipe2" {
                if let Some(Expr::Reference(reference)) = call.args.first_mut() {
                    if let Expr::Index(indexed) = reference.expr.as_ref() {
                        if matches!(indexed.index.as_ref(), Expr::Lit(lit) if matches!(&lit.lit, syn::Lit::Int(n) if n.base10_digits() == "0"))
                        {
                            let base = &indexed.expr;
                            let source: Expr = parse_quote!((#base).as_mut_ptr());
                            call.args[0] = source;
                        }
                    }
                }
            }
            let words: Vec<_> = native
                .types
                .iter()
                .zip(&call.args)
                .map(|(kind, arg)| self.word(kind, arg))
                .collect();
            let func = format_ident!("llmlang_syscall_{}", native.name);
            *expr = parse_quote!(unsafe { #func(#(#words),*) });
            return;
        }
        match name.as_str() {
            "size_of" => {
                let last = callee.path.segments.last().unwrap();
                call.func = Box::new(parse_quote!(std::mem::#last));
            }
            "trap" if call.args.is_empty() => {
                *expr = parse_quote!(std::process::abort());
            }
            "CString::from_bytes" if call.args.len() == 1 => {
                let arg = &call.args[0];
                *expr = parse_quote!(CString::new((#arg).as_slice()));
            }
            "sockaddr_in::loopback" => {}
            _ => self.reject(format!(
                "call is outside the native profile or has no pin: {name}"
            )),
        }
    }
}

pub(super) struct Output {
    pub source: String,
    pub executable: bool,
    pub exports: Value,
}

pub(super) fn lower(
    package_name: &str,
    package: &Package,
    exports: &BTreeMap<String, String>,
    allowed: &BTreeSet<(String, String)>,
) -> Result<Output> {
    let main_name = format!("{package_name}.main");
    let main = exports.get(&main_name);
    let mut source = String::from(include_str!("native_runtime.rs"));
    let mut reachable = BTreeMap::new();
    let mut symbols = BTreeMap::new();
    for (export, implementation) in exports {
        let row = &package.tables["functions"][implementation];
        if Some(implementation) == main && export == &main_name {
            let body = &row["canonical_body"];
            let text = body["source"]
                .as_str()
                .ok_or_else(|| invalid("native main requires a source body"))?;
            let calls = pinned_calls(package, body, allowed)?;
            let mut function: syn::ItemFn = syn::parse_str(text).map_err(validation)?;
            let signature = &row["typed_signature"];
            let params = signature["parameters"]
                .as_array()
                .ok_or_else(|| invalid("missing main signature"))?;
            let output = &function.sig.output;
            if function.sig.ident != "main"
                || quote!(#output).to_string() != "-> ExitStatus"
                || signature["result"] != "ExitStatus"
                || params.len() != function.sig.inputs.len()
                || function.sig.unsafety.is_some()
                || function.sig.abi.is_some()
                || function.sig.asyncness.is_some()
                || function.sig.constness.is_some()
                || !function.sig.generics.params.is_empty()
            {
                return Err(invalid("expected ordinary main with an ADR-032 signature"));
            }
            let arguments = match params.as_slice() {
                [] => quote!(),
                [param] if param["type"] == "LaunchArgs" => {
                    let input = function.sig.inputs.first().unwrap();
                    let expected: syn::FnArg = syn::parse_str(&format!(
                        "{}: LaunchArgs",
                        param["name"].as_str().unwrap_or("")
                    ))
                    .map_err(validation)?;
                    if input.to_token_stream().to_string() != expected.to_token_stream().to_string()
                    {
                        return Err(invalid(
                            "main source disagrees with its LaunchArgs signature",
                        ));
                    }
                    quote!(std::env::args_os()
                        .skip(1)
                        .map(std::os::unix::ffi::OsStringExt::into_vec)
                        .collect())
                }
                _ => return Err(invalid("unsupported ordinary main parameters")),
            };
            let mut lower = Lower {
                calls: &calls,
                used: BTreeSet::new(),
                error: None,
            };
            lower.visit_item_fn_mut(&mut function);
            if let Some(error) = lower.error {
                return Err(error);
            }
            if lower.used.len() != calls.len() {
                return Err(invalid("unused pin in native main"));
            }
            reachable.extend(calls);
            function.sig.ident = format_ident!("llmlang_main");
            source.push_str(
                &quote! {
                    #function
                    fn main() { std::process::exit(llmlang_main(#arguments)); }
                }
                .to_string(),
            );
        } else {
            let call = native_call(row)?;
            let symbol = format!("llmlang_syscall_{}", call.name);
            symbols.insert(export, symbol);
            reachable.insert(call.name.clone(), call);
        }
    }
    if exports.is_empty() {
        return Err(invalid("package has no public bindings"));
    }
    for call in reachable.into_values() {
        let name = format_ident!("llmlang_syscall_{}", call.name);
        let number = call.number;
        let params: Vec<_> = (0..call.types.len())
            .map(|index| format_ident!("word_{index}"))
            .collect();
        let words: Vec<_> = (0..6)
            .map(|index| {
                params
                    .get(index)
                    .map_or_else(|| quote!(0), |id| quote!(#id))
            })
            .collect();
        source.push_str(
            &quote! {
                pub unsafe fn #name(#(#params: usize),*) -> isize {
                    unsafe { raw_syscall(#number as usize, [#(#words),*]) }
                }
            }
            .to_string(),
        );
    }
    Ok(Output {
        source,
        executable: main.is_some(),
        exports: json!(symbols),
    })
}

pub(super) fn compile(output: &Output, artifact: &Path) -> Result<()> {
    let directory = tempfile::tempdir()?;
    let source = directory.path().join("package.rs");
    fs::write(&source, &output.source)?;
    let result = Command::new(std::env::var_os("RUSTC").unwrap_or_else(|| "rustc".into()))
        .current_dir(directory.path())
        .args([
            "--edition=2021",
            "--target",
            "x86_64-unknown-linux-gnu",
            "--crate-name",
            "llmlang_native",
            "--crate-type",
            if output.executable { "bin" } else { "rlib" },
            "-C",
            "overflow-checks=yes",
            "-o",
        ])
        .arg(artifact)
        .arg(&source)
        .output()?;
    if !result.status.success() {
        return Err(ServerError::new(
            "BuildFailed",
            String::from_utf8_lossy(&result.stderr).trim(),
        ));
    }
    Ok(())
}
