//! Lower the native Linux x86-64 profile to a temporary Rust translation unit.

use super::{
    invalid,
    obligations::{CallsByCaller, ResolvedCall},
    validation, Package, Path, Result, ServerError,
};
use quote::{format_ident, quote};
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
struct Syscall {
    name: String,
    implementation: String,
    number: u16,
    types: Vec<String>,
}

#[derive(Clone)]
enum Call {
    Syscall(Syscall),
    Source {
        implementation: String,
        arity: usize,
        raw_abi: bool,
    },
}

fn source_symbol(implementation: &str) -> syn::Ident {
    format_ident!(
        "llmlang_source_{}",
        implementation.trim_start_matches("sha256:")
    )
}

fn native_call(name: &str, package: &Package, row: &Value) -> Result<Syscall> {
    let body = row["canonical_body"]
        .as_str()
        .ok_or_else(|| invalid("expected native syscall source"))?;
    let signature = package.function_signature(row).map_err(validation)?.typed;
    if !identifier(name) || signature["result"] != "AbiResult" {
        return Err(invalid("unsupported native syscall signature"));
    }
    let mut names = Vec::new();
    let mut types = Vec::new();
    let params = signature["parameters"]
        .as_array()
        .ok_or_else(|| invalid("missing native parameters"))?;
    if params.len() > 6 {
        return Err(invalid("unsupported syscall arity"));
    }
    for parameter in params {
        let param = parameter["name"]
            .as_str()
            .filter(|param| identifier(param))
            .ok_or_else(|| invalid("invalid native parameter name"))?;
        let kind = parameter["type"]
            .as_str()
            .ok_or_else(|| invalid("missing native parameter type"))?;
        if names.contains(&param) {
            return Err(invalid("duplicate native parameter"));
        }
        names.push(param);
        types.push(kind.to_owned());
    }
    let args = body
        .trim()
        .strip_prefix('{')
        .and_then(|body| body.strip_suffix('}'))
        .and_then(|body| body.trim().strip_prefix("stdlib::syscall("))
        .and_then(|body| body.strip_suffix(')'))
        .ok_or_else(|| invalid("expected stdlib::syscall in a body-only block"))?;
    let mut args = args.split(',').map(str::trim);
    let number = args
        .next()
        .and_then(|number| number.parse().ok())
        .ok_or_else(|| invalid("invalid syscall number"))?;
    if matches!(number, 15 | 58 | 335) {
        return Err(invalid(
            "syscall requires its dedicated continuation profile",
        ));
    }
    if args.ne(names) {
        return Err(invalid(format!(
            "{name}: syscall operands disagree with signature"
        )));
    }
    Ok(Syscall {
        name: name.into(),
        implementation: row["impl_hash"]
            .as_str()
            .ok_or_else(|| invalid("missing syscall identity"))?
            .into(),
        number,
        types,
    })
}

fn is_syscall_wrapper(row: &Value) -> bool {
    row["canonical_body"].as_str().is_some_and(|body| {
        body.trim()
            .strip_prefix('{')
            .is_some_and(|body| body.trim_start().starts_with("stdlib::syscall("))
    })
}

fn identifier(name: &str) -> bool {
    let mut bytes = name.bytes();
    !name.starts_with("builtin__")
        && bytes
            .next()
            .is_some_and(|byte| byte.is_ascii_alphabetic() || byte == b'_')
        && bytes.all(|byte| byte.is_ascii_alphanumeric() || byte == b'_')
}

pub(super) type CallBindings = BTreeMap<String, (String, String)>;

fn resolve_source(
    package: &Package,
    row: &Value,
    bindings: &CallBindings,
) -> Result<(BTreeMap<String, Call>, BTreeSet<ResolvedCall>)> {
    let text = row["canonical_body"]
        .as_str()
        .ok_or_else(|| invalid("native implementation requires plain source"))?;
    let mut calls = BTreeMap::new();
    let mut resolved = BTreeMap::new();
    for obligation in package.tables["verification_obligations"]
        .values()
        .filter(|obligation| {
            obligation["kind"] == "call_compatibility"
                && obligation["caller_impl_hash"] == row["impl_hash"]
        })
    {
        let implementation = obligation["callee_impl_hash"]
            .as_str()
            .ok_or_else(|| invalid("missing native callee pin"))?;
        let contract = obligation["caller_required_contract_hash"]
            .as_str()
            .ok_or_else(|| invalid("missing native contract pin"))?;
        let mut matches = bindings
            .iter()
            .filter(|(_, (callee, required))| callee == implementation && required == contract);
        let (qualified, _) = matches
            .next()
            .ok_or_else(|| invalid("native call is absent from public bindings"))?;
        if matches.next().is_some() {
            return Err(invalid("ambiguous native call binding"));
        }
        let (_, name) = qualified
            .rsplit_once('.')
            .ok_or_else(|| invalid("missing native namespace"))?;
        let callee = package.tables["functions"]
            .get(implementation)
            .ok_or_else(|| invalid("unresolved native implementation"))?;
        if callee["provided_contract_hash"] != contract {
            return Err(invalid("native binding must select the exact contract"));
        }
        let signature = package
            .function_signature(callee)
            .map_err(validation)?
            .typed;
        let call = if is_syscall_wrapper(callee) {
            Call::Syscall(native_call(name, package, callee)?)
        } else {
            let params = signature["parameters"]
                .as_array()
                .ok_or_else(|| invalid("missing native parameters"))?;
            Call::Source {
                implementation: implementation.into(),
                arity: params.len(),
                raw_abi: signature["result"] == "AbiResult",
            }
        };
        if calls.insert(name.to_owned(), call).is_some() {
            return Err(invalid("ambiguous native call name"));
        }
        resolved.insert(
            name,
            ResolvedCall {
                callee_impl_hash: implementation.into(),
                required_contract_hash: contract.into(),
            },
        );
    }
    let material = json!({
        "typed_signature": package.function_signature(row).map_err(validation)?.typed,
        "canonical_body": text,
        "provided_contract_hash": row["provided_contract_hash"],
        "resolved_calls": resolved.values().collect::<Vec<_>>(),
    });
    let identity = format!(
        "sha256:{}",
        super::hash(&("llmlang-native-source-impl/v1", material))?
    );
    if row["impl_hash"] != identity {
        return Err(validation(
            "native source or resolved call identity mismatch",
        ));
    }
    Ok((calls, resolved.into_values().collect()))
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
        if let Some(Call::Source {
            implementation,
            arity,
            raw_abi,
        }) = self.calls.get(&name)
        {
            if call.args.len() != *arity {
                self.reject(format!("{name}: wrong native argument count"));
                return;
            }
            self.used.insert(name);
            let symbol = source_symbol(implementation);
            if *raw_abi {
                let args = &call.args;
                *expr = parse_quote!(unsafe { #symbol(#args) });
            } else {
                call.func = Box::new(parse_quote!(#symbol));
            }
            return;
        }
        if let Some(Call::Syscall(native)) = self.calls.get(&name).cloned() {
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
            "builtin__size_of" if call.args.is_empty() => {
                let generics = &callee.path.segments.last().unwrap().arguments;
                call.func = Box::new(parse_quote!(std::mem::size_of #generics));
            }
            "builtin__trap" if call.args.is_empty() => {
                *expr = parse_quote!(std::process::abort());
            }
            "builtin__cstring_from_bytes" if call.args.len() == 1 => {
                let arg = &call.args[0];
                *expr = parse_quote!(CString::new((#arg).as_slice()));
            }
            "builtin__errno_message" if call.args.len() == 1 => {
                call.func = Box::new(parse_quote!(errno_message));
            }
            "builtin__sockaddr_in_loopback" if call.args.len() == 1 => {
                call.func = Box::new(parse_quote!(sockaddr_in::loopback));
            }
            "builtin__syscall" if call.args.len() == 7 => {
                let mut args = call.args.iter();
                let number = args.next().unwrap();
                *expr = parse_quote!(unsafe { invoke_syscall(#number, [#(#args),*]) });
            }
            "builtin__write_utf8" if call.args.len() == 2 => {
                call.func = Box::new(parse_quote!(write_utf8));
            }
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
    pub calls: CallsByCaller,
}

fn lower_body(
    package: &Package,
    row: &Value,
    bindings: &CallBindings,
    syscalls: &mut BTreeMap<String, Syscall>,
    pending: &mut BTreeSet<String>,
) -> Result<(syn::Block, BTreeSet<ResolvedCall>)> {
    let (calls, resolved) = resolve_source(package, row, bindings)?;
    let mut body = syn::parse_str(row["canonical_body"].as_str().unwrap()).map_err(validation)?;
    let mut lower = Lower {
        calls: &calls,
        used: BTreeSet::new(),
        error: None,
    };
    lower.visit_block_mut(&mut body);
    if let Some(error) = lower.error {
        return Err(error);
    }
    if lower.used.len() != calls.len() {
        return Err(invalid("unused pin in native implementation"));
    }
    for call in calls.into_values() {
        match call {
            Call::Syscall(call) => {
                syscalls.insert(call.name.clone(), call);
            }
            Call::Source { implementation, .. } => {
                pending.insert(implementation);
            }
        }
    }
    Ok((body, resolved))
}

fn library_type(kind: &Value, parameter: bool) -> Result<Type> {
    match (kind.as_str(), parameter) {
        (Some("I32"), _) => Ok(parse_quote!(I32)),
        (Some("Usize"), true) => Ok(parse_quote!(Usize)),
        (Some("AbiResult"), false) => Ok(parse_quote!(AbiResult)),
        (Some("Utf8"), true) => Ok(parse_quote!(Utf8<'_>)),
        (Some("IoResult"), false) => Ok(parse_quote!(IoResult)),
        _ => Err(invalid("unsupported native library type")),
    }
}

fn syscall_target(
    package: &Package,
    row: &Value,
    bindings: &CallBindings,
) -> Result<(String, BTreeSet<ResolvedCall>)> {
    let (calls, resolved) = resolve_source(package, row, bindings)?;
    let Some(Call::Source {
        implementation,
        arity: 7,
        raw_abi: true,
    }) = calls.get("syscall")
    else {
        return Err(invalid("native syscall wrapper must pin stdlib.syscall"));
    };
    if calls.len() != 1 || bindings.get("stdlib.syscall").map(|(id, _)| id) != Some(implementation)
    {
        return Err(invalid(
            "native syscall wrapper must pin only stdlib.syscall",
        ));
    }
    Ok((implementation.clone(), resolved))
}

pub(super) fn lower(
    package_name: &str,
    package: &Package,
    local_functions: &BTreeMap<String, Value>,
    exports: &BTreeMap<String, String>,
    bindings: &CallBindings,
) -> Result<Output> {
    if exports.is_empty() {
        return Err(invalid("package has no public bindings"));
    }
    let main_name = format!("{package_name}.main");
    let main = exports.get(&main_name);
    let mut source = String::from(include_str!("native_runtime.rs"));
    let mut reachable = BTreeMap::new();
    let mut pending = BTreeSet::new();
    let mut symbols = BTreeMap::new();
    let mut resolved_calls = BTreeMap::new();
    let mut emitted = BTreeSet::new();
    let mut public_sources = BTreeSet::new();
    let mut emitted_syscalls = BTreeSet::new();
    for (export, implementation) in exports {
        let row = &package.tables["functions"][implementation];
        let signature = package.function_signature(row).map_err(validation)?.typed;
        if export == &main_name {
            let (body, resolved) =
                lower_body(package, row, bindings, &mut reachable, &mut pending)?;
            resolved_calls.insert(implementation.clone(), resolved);
            let params = signature["parameters"]
                .as_array()
                .ok_or_else(|| invalid("missing main signature"))?;
            if signature["result"] != "ExitStatus" {
                return Err(invalid("expected ordinary main with an ADR-032 signature"));
            }
            let (declaration, arguments) = match params.as_slice() {
                [] => (quote!(), quote!()),
                [param] if param["type"] == "LaunchArgs" => {
                    let name: syn::Ident =
                        syn::parse_str(param["name"].as_str().unwrap_or("")).map_err(validation)?;
                    (
                        quote!(#name: LaunchArgs),
                        quote!(std::env::args_os()
                            .skip(1)
                            .map(std::os::unix::ffi::OsStringExt::into_vec)
                            .collect()),
                    )
                }
                _ => return Err(invalid("unsupported ordinary main parameters")),
            };
            source.push_str(
                &quote! {
                    fn llmlang_main(#declaration) -> ExitStatus #body
                    fn main() { std::process::exit(llmlang_main(#arguments)); }
                }
                .to_string(),
            );
        } else if is_syscall_wrapper(row) {
            let (_, name) = export
                .rsplit_once('.')
                .ok_or_else(|| invalid("missing native namespace"))?;
            let call = native_call(name, package, row)?;
            symbols.insert(export, format!("llmlang_syscall_{}", call.name));
            reachable.insert(call.name.clone(), call);
        } else {
            symbols.insert(export, source_symbol(implementation).to_string());
            pending.insert(implementation.clone());
            public_sources.insert(implementation.clone());
        }
    }
    while !reachable.is_empty() || !pending.is_empty() {
        if let Some((_, call)) = reachable.pop_first() {
            if !emitted_syscalls.insert(call.name.clone()) {
                continue;
            }
            let row = &package.tables["functions"][&call.implementation];
            let (implementation, resolved) = syscall_target(package, row, bindings)?;
            let target = source_symbol(&implementation);
            pending.insert(implementation);
            resolved_calls.insert(call.implementation, resolved);
            let name = format_ident!("llmlang_syscall_{}", call.name);
            let number = call.number;
            let params: Vec<_> = (0..call.types.len())
                .map(|index| format_ident!("word_{index}"))
                .collect();
            let words = (0..6).map(|index| {
                params
                    .get(index)
                    .map_or_else(|| quote!(0), |id| quote!(#id))
            });
            source.push_str(
                &quote! {
                    pub unsafe fn #name(#(#params: usize),*) -> isize {
                        unsafe { #target(#number as usize, #(#words),*) }
                    }
                }
                .to_string(),
            );
            continue;
        }
        let implementation = pending.pop_first().unwrap();
        if !emitted.insert(implementation.clone()) {
            continue;
        }
        let row = &package.tables["functions"][&implementation];
        let (body, resolved) = lower_body(package, row, bindings, &mut reachable, &mut pending)?;
        let signature = package.function_signature(row).map_err(validation)?.typed;
        let parameters = signature["parameters"]
            .as_array()
            .ok_or_else(|| invalid("missing native library parameters"))?
            .iter()
            .map(|parameter| {
                let name: syn::Ident =
                    syn::parse_str(parameter["name"].as_str().unwrap_or("")).map_err(validation)?;
                let kind = library_type(&parameter["type"], true)?;
                Ok(quote!(#name: #kind))
            })
            .collect::<Result<Vec<_>>>()?;
        let result = library_type(&signature["result"], false)?;
        let safety = (signature["result"] == "AbiResult").then(|| quote!(unsafe));
        let symbol = source_symbol(&implementation);
        let visibility = if public_sources.contains(&implementation) {
            quote!(pub)
        } else {
            quote!()
        };
        resolved_calls.insert(implementation, resolved);
        source.push_str(
            &quote!(#visibility #safety fn #symbol(#(#parameters),*) -> #result #body).to_string(),
        );
    }
    // Preserve and check the call links for unbound continuation entries without emitting them.
    for (implementation, row) in local_functions {
        if is_syscall_wrapper(row) && !resolved_calls.contains_key(implementation) {
            let (_, resolved) = syscall_target(package, row, bindings)?;
            resolved_calls.insert(implementation.clone(), resolved);
        }
    }
    Ok(Output {
        source,
        executable: main.is_some(),
        exports: json!(symbols),
        calls: resolved_calls,
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
