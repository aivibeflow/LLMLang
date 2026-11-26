//! Lower the native Linux x86-64 profile to a temporary Rust translation unit.

use super::{
    invalid,
    obligations::{CallsByCaller, ResolvedCall},
    validation, Package, Path, Result, ServerError,
};
use quote::{format_ident, quote};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
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

fn native_call(name: &str, package: &Package, row: &Value) -> Result<Call> {
    let body = row["canonical_body"]
        .as_str()
        .ok_or_else(|| invalid("expected native syscall source"))?;
    let signature = package.function_signature(row).map_err(validation)?.typed;
    // Preserve the implementation's semantic hash across storage profiles.
    let identity_input = json!({
        "typed_signature": signature,
        "canonical_body": body,
        "provided_contract_hash": row["provided_contract_hash"],
    });
    let mut identity = Sha256::new();
    identity.update(b"llmlang-native-projection-impl/v1\0");
    identity.update(serde_json::to_vec(&identity_input)?);
    if row["impl_hash"] != format!("sha256:{:x}", identity.finalize()) {
        return Err(validation(
            "native syscall implementation identity mismatch",
        ));
    }
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
        .and_then(|body| body.trim().strip_prefix("syscall("))
        .and_then(|body| body.strip_suffix(')'))
        .ok_or_else(|| invalid("expected a syscall in a body-only block"))?;
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

pub(super) type CallBindings = BTreeMap<String, (String, String)>;

fn resolve_source(
    package: &Package,
    row: &Value,
    bindings: &CallBindings,
) -> Result<(syn::Block, BTreeMap<String, Call>, BTreeSet<ResolvedCall>)> {
    let text = row["canonical_body"]
        .as_str()
        .ok_or_else(|| invalid("native main requires plain source"))?;
    let block = syn::parse_str(text).map_err(validation)?;
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
            return Err(invalid(
                "native binding must select the exact syscall contract",
            ));
        }
        let call = native_call(name, package, callee)?;
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
    Ok((block, calls, resolved.into_values().collect()))
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
    pub calls: CallsByCaller,
}

pub(super) fn lower(
    package_name: &str,
    package: &Package,
    exports: &BTreeMap<String, String>,
    bindings: &CallBindings,
) -> Result<Output> {
    let main_name = format!("{package_name}.main");
    let main = exports.get(&main_name);
    let mut source = String::from(include_str!("native_runtime.rs"));
    let mut reachable = BTreeMap::new();
    let mut symbols = BTreeMap::new();
    let mut resolved_calls = BTreeMap::new();
    for (export, implementation) in exports {
        let row = &package.tables["functions"][implementation];
        if Some(implementation) == main && export == &main_name {
            let (mut body, calls, resolved) = resolve_source(package, row, bindings)?;
            resolved_calls.insert(implementation.clone(), resolved);
            let signature = package.function_signature(row).map_err(validation)?.typed;
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
                return Err(invalid("unused pin in native main"));
            }
            reachable.extend(calls);
            source.push_str(
                &quote! {
                    fn llmlang_main(#declaration) -> ExitStatus #body
                    fn main() { std::process::exit(llmlang_main(#arguments)); }
                }
                .to_string(),
            );
        } else {
            let (_, name) = export
                .rsplit_once('.')
                .ok_or_else(|| invalid("missing native namespace"))?;
            let call = native_call(name, package, row)?;
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
