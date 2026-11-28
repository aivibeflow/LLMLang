//! Lower a package to a temporary Rust translation unit for Linux x86-64.

use super::{
    invalid,
    obligations::{CallsByCaller, ResolvedCall},
    validation, Package, Path, Result, ServerError, BUILTIN,
};
use proc_macro2::{TokenStream, TokenTree};
use quote::{format_ident, quote};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, BTreeSet},
    ffi::OsString,
    fs,
    path::PathBuf,
    process::Command,
};
use syn::{
    parse_quote,
    visit_mut::{self, VisitMut},
    Expr, Item, Type,
};

pub(super) fn referenced_builtin(source: &str) -> Result<Option<String>> {
    find_builtin(source, |name| name.starts_with("builtin__"))
}

fn find_builtin(source: &str, matches: impl Fn(&str) -> bool) -> Result<Option<String>> {
    // The native profile includes syscall operands such as `type` that lex as
    // identifiers but are not valid Rust expressions.
    let tokens = source.parse().map_err(validation)?;
    Ok(builtin_in_tokens(tokens, &matches))
}

fn builtin_in_tokens(tokens: TokenStream, matches: &impl Fn(&str) -> bool) -> Option<String> {
    tokens.into_iter().find_map(|token| match token {
        TokenTree::Ident(identifier) => {
            let spelling = identifier.to_string();
            let name = spelling.strip_prefix("r#").unwrap_or(&spelling);
            matches(name).then(|| name.to_owned())
        }
        TokenTree::Group(group) => builtin_in_tokens(group.stream(), matches),
        _ => None,
    })
}

#[derive(Clone)]
struct Syscall {
    name: String,
    implementation: String,
    number: u16,
    types: Vec<String>,
}

impl Syscall {
    fn symbol(&self) -> syn::Ident {
        format_ident!(
            "llmlang_syscall_{}__{}",
            self.name,
            self.implementation.trim_start_matches("sha256:")
        )
    }
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

pub(super) fn source_symbol(implementation: &str) -> syn::Ident {
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
        .and_then(|body| body.trim().strip_prefix("builtin::syscall("))
        .and_then(|body| body.strip_suffix(')'))
        .ok_or_else(|| invalid("expected builtin::syscall in a body-only block"))?;
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

fn is_syscall_wrapper(package_name: &str, row: &Value) -> bool {
    package_name == "linux.syscalls"
        && row["canonical_body"].as_str().is_some_and(|body| {
            body.trim()
                .strip_prefix('{')
                .is_some_and(|body| body.trim_start().starts_with("builtin::syscall("))
        })
}

pub(super) fn requires_platform(owner: &str, row: &Value) -> Result<bool> {
    Ok(is_syscall_wrapper(owner, row)
        || (owner == BUILTIN
            && find_builtin(row["canonical_body"].as_str().unwrap_or_default(), |name| {
                name == "builtin__syscall"
            })?
            .is_some()))
}

fn identifier(name: &str) -> bool {
    let mut bytes = name.bytes();
    !name.starts_with("builtin__")
        && bytes
            .next()
            .is_some_and(|byte| byte.is_ascii_alphabetic() || byte == b'_')
        && bytes.all(|byte| byte.is_ascii_alphanumeric() || byte == b'_')
}

pub(super) type Target<'a> = (&'a str, &'a str);
pub(super) const LINUX_X86_64: Target<'static> = ("x86_64", "linux");

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, serde::Serialize)]
pub(super) struct InterfacePin {
    pub name: String,
    pub version_hash: String,
    pub interface_hash: String,
    pub required_contract_hash: String,
}

#[derive(Clone)]
pub(super) struct InterfaceBinding {
    pub pin: InterfacePin,
    pub version: String,
    pub implementations: BTreeMap<String, BTreeMap<String, String>>,
}

impl InterfaceBinding {
    pub fn select(&self, (arch, os): Target<'_>) -> Result<(Target<'_>, &str)> {
        let lookup = |arch: &str, os: &str| {
            let (arch, rows) = self.implementations.get_key_value(arch)?;
            let (os, implementation) = rows.get_key_value(os)?;
            Some(((arch.as_str(), os.as_str()), implementation.as_str()))
        };

        if let Some(exact) = lookup(arch, os) {
            return Ok(exact);
        }
        match (lookup(arch, ""), lookup("", os)) {
            (Some(_), Some(_)) => Err(ServerError::new(
                "AmbiguousBinding",
                format!(
                    "{} at version {} matches both ({arch:?}, \"\") and (\"\", {os:?})",
                    self.pin.name, self.version,
                ),
            )),
            (Some(binding), None) | (None, Some(binding)) => Ok(binding),
            (None, None) => lookup("", "").ok_or_else(|| {
                ServerError::new(
                    "MissingImplementation",
                    format!(
                        "{} at version {} has no binding for ({arch}, {os})",
                        self.pin.name, self.version,
                    ),
                )
            }),
        }
    }
}

pub(super) type Catalog = BTreeMap<String, InterfaceBinding>;
pub(super) type CallBindings = BTreeMap<String, std::sync::Arc<Catalog>>;

fn call_spelling(path: &syn::Path) -> String {
    path.segments
        .iter()
        .map(|part| part.ident.to_string())
        .collect::<Vec<_>>()
        .join("::")
}

#[derive(Default)]
struct SourceCalls {
    names: BTreeSet<String>,
    direct: BTreeSet<ResolvedCall>,
    error: Option<ServerError>,
}

fn direct_pin(call: &syn::ExprCall) -> Result<ResolvedCall> {
    use syn::spanned::Spanned;
    let mut args = call.args.iter();
    Ok(ResolvedCall {
        callee_impl_hash: super::scalar_source::exact_hash(
            args.next(),
            call.span(),
            "implementation",
        )?,
        required_contract_hash: super::scalar_source::exact_hash(
            args.next(),
            call.span(),
            "contract",
        )?,
        binding: None,
    })
}

impl VisitMut for SourceCalls {
    fn visit_expr_call_mut(&mut self, call: &mut syn::ExprCall) {
        if let Expr::Path(path) = call.func.as_ref() {
            let name = call_spelling(&path.path);
            if name == "call" {
                match direct_pin(call) {
                    Ok(pin) => {
                        self.direct.insert(pin);
                    }
                    Err(error) => {
                        self.error.get_or_insert(error);
                    }
                }
            } else {
                self.names.insert(name);
            }
        }
        visit_mut::visit_expr_call_mut(self, call);
    }
}

fn source_calls(owner: &str, row: &Value) -> Result<SourceCalls> {
    let source = row["canonical_body"]
        .as_str()
        .ok_or_else(|| invalid("native implementation requires plain source"))?;
    let mut calls = SourceCalls::default();
    if is_syscall_wrapper(owner, row) {
        // Some ABI operand names are reserved Rust words.
        calls.names.insert("builtin::syscall".into());
        if source.trim() == "{\n    builtin::syscall(15); builtin::trap()\n}" {
            calls.names.insert("builtin::trap".into());
        }
    } else {
        let mut body: syn::Block = syn::parse_str(source).map_err(validation)?;
        calls.visit_block_mut(&mut body);
    }
    if let Some(error) = calls.error.take() {
        return Err(error);
    }
    Ok(calls)
}

fn interface_calls<'a>(
    names: BTreeSet<String>,
    catalog: &'a Catalog,
) -> Result<BTreeMap<String, &'a InterfaceBinding>> {
    names
        .into_iter()
        .filter(|name| !name.starts_with("builtin__"))
        .map(|name| {
            let mut matches = catalog.values().filter(|binding| {
                let (namespace, symbol) = binding.pin.name.rsplit_once('.').unwrap();
                name == binding.pin.name.replace('.', "::")
                    || (namespace != BUILTIN && name == symbol)
            });
            let binding = matches.next().ok_or_else(|| {
                invalid(format!(
                    "call is outside the native profile or has no interface: {name}"
                ))
            })?;
            if matches.next().is_some() {
                return Err(invalid(format!("ambiguous native interface call {name}")));
            }
            Ok((name, binding))
        })
        .collect()
}

pub(super) fn implementation_identity(
    owner: &str,
    package: &Package,
    row: &Value,
    catalog: &Catalog,
) -> Result<String> {
    let calls = interface_calls(source_calls(owner, row)?.names, catalog)?;
    let material = json!({
        "typed_signature": package.function_signature(row).map_err(validation)?.typed,
        "canonical_body": row["canonical_body"],
        "provided_contract_hash": row["provided_contract_hash"],
        "interface_calls": calls.iter().map(|(name, binding)| (name, &binding.pin)).collect::<BTreeMap<_, _>>(),
    });
    Ok(format!(
        "sha256:{}",
        super::hash(&("llmlang-native-source-impl/v2", material))?
    ))
}

fn resolve_source(
    owner: &str,
    package: &Package,
    row: &Value,
    bindings: &CallBindings,
    target: Target<'_>,
) -> Result<(BTreeMap<String, Call>, BTreeSet<ResolvedCall>)> {
    let catalog = bindings
        .get(row["impl_hash"].as_str().unwrap())
        .ok_or_else(|| validation("missing native interface catalog"))?;
    let mut calls = BTreeMap::new();
    let source = source_calls(owner, row)?;
    let mut resolved = source.direct;
    for pin in &resolved {
        let callee = package.tables["functions"]
            .get(&pin.callee_impl_hash)
            .ok_or_else(|| validation("missing direct callee"))?;
        if is_syscall_wrapper("linux.syscalls", callee)
            || requires_platform(super::BUILTIN, callee)?
        {
            return Err(validation("platform-dependent calls require a binding"));
        }
        let required = package.tables["contracts"]
            .get(&pin.required_contract_hash)
            .ok_or_else(|| validation("missing required direct call contract"))?;
        if required["contract_kind"] != "function" {
            return Err(validation("direct call requires a function contract"));
        }
    }
    for (source_name, binding) in interface_calls(source.names, catalog)? {
        let ((binding_arch, binding_os), implementation) = binding.select(target)?;
        let (namespace, name) = binding.pin.name.rsplit_once('.').unwrap();
        let contract = &binding.pin.required_contract_hash;
        let callee = package.tables["functions"]
            .get(implementation)
            .ok_or_else(|| invalid("unresolved native implementation"))?;
        let signature = package
            .function_signature(callee)
            .map_err(validation)?
            .typed;
        let call = if is_syscall_wrapper(namespace, callee) {
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
        calls.insert(source_name, call);
        resolved.insert(ResolvedCall {
            callee_impl_hash: implementation.into(),
            required_contract_hash: contract.clone(),
            binding: Some(super::obligations::ResolvedBinding {
                target_arch: target.0.into(),
                target_os: target.1.into(),
                binding_arch: binding_arch.into(),
                binding_os: binding_os.into(),
                interface: binding.pin.clone(),
            }),
        });
    }
    Ok((calls, resolved))
}

pub(super) fn resolved_calls(
    owner: &str,
    package: &Package,
    row: &Value,
    bindings: &CallBindings,
    target: Target<'_>,
) -> Result<BTreeSet<ResolvedCall>> {
    Ok(resolve_source(owner, package, row, bindings, target)?.1)
}

#[derive(Default)]
struct RuntimeRequirements {
    builtins: BTreeSet<String>,
    requires_std: bool,
}

impl RuntimeRequirements {
    fn freestanding(&self) -> bool {
        !self.requires_std
            && self.builtins.contains("builtin__syscall")
            && self.builtins.iter().all(|name| {
                matches!(
                    name.as_str(),
                    "builtin__syscall"
                        | "builtin__size_of"
                        | "builtin__sockaddr_in_loopback"
                        | "builtin__write_utf8"
                )
            })
    }
}

struct Lower<'a> {
    calls: &'a BTreeMap<String, Call>,
    used: BTreeSet<String>,
    requirements: &'a mut RuntimeRequirements,
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

    fn visit_path_mut(&mut self, path: &mut syn::Path) {
        if path.segments.first().is_some_and(|segment| {
            matches!(
                segment.ident.to_string().as_str(),
                "std" | "Vec" | "String" | "CString" | "LaunchArgs"
            )
        }) {
            self.requirements.requires_std = true;
        }
        visit_mut::visit_path_mut(self, path);
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
                    *value = parse_quote!(core::ptr::null::<core::ffi::c_char>());
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
        let name = call_spelling(&callee.path);
        if name == "call" {
            match direct_pin(call) {
                Ok(pin) => {
                    let target = source_symbol(&pin.callee_impl_hash);
                    let arguments = call.args.iter().skip(2);
                    *expr = parse_quote!(#target(#(#arguments),*));
                }
                Err(error) => {
                    self.error.get_or_insert(error);
                }
            }
            return;
        }
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
            let func = native.symbol();
            *expr = parse_quote!(unsafe { #func(#(#words),*) });
            return;
        }
        if name.starts_with("builtin__") {
            self.requirements.builtins.insert(name.clone());
        }
        match name.as_str() {
            "builtin__size_of" if call.args.is_empty() => {
                let generics = &callee.path.segments.last().unwrap().arguments;
                call.func = Box::new(parse_quote!(core::mem::size_of #generics));
            }
            "builtin__trap" if call.args.is_empty() => {
                *expr = parse_quote!(std::process::abort());
            }
            "builtin__cstring_from_bytes" if call.args.len() == 1 => {
                let arg = &call.args[0];
                *expr = parse_quote!(CString::new(#arg));
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
    freestanding: bool,
    pub exports: Value,
    pub calls: CallsByCaller,
}

fn lower_body(
    package: &Package,
    row: &Value,
    bindings: &CallBindings,
    target: Target<'_>,
    syscalls: &mut BTreeMap<syn::Ident, Syscall>,
    pending: &mut BTreeSet<String>,
    requirements: &mut RuntimeRequirements,
) -> Result<(syn::Block, BTreeSet<ResolvedCall>)> {
    if super::scalar_source::supported_signature(package, row) {
        let body = super::scalar_source::body(package, row)?;
        let mut resolved = BTreeSet::new();
        super::obligations::collect_pins(&body, &mut resolved);
        pending.extend(resolved.iter().map(|call| call.callee_impl_hash.clone()));
        return Ok((super::scalar_source::compile(&body)?, resolved));
    }
    let (calls, resolved) = resolve_source("", package, row, bindings, target)?;
    let mut body = syn::parse_str(row["canonical_body"].as_str().unwrap()).map_err(validation)?;
    let mut lower = Lower {
        calls: &calls,
        used: BTreeSet::new(),
        requirements,
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
                syscalls.insert(call.symbol(), call);
            }
            Call::Source { implementation, .. } => {
                pending.insert(implementation);
            }
        }
    }
    pending.extend(
        resolved
            .iter()
            .filter(|call| call.binding.is_none())
            .map(|call| call.callee_impl_hash.clone()),
    );
    Ok((body, resolved))
}

fn library_type(kind: &Value, parameter: bool) -> Result<Type> {
    match (kind.as_str(), parameter) {
        (Some("I64"), _) => Ok(parse_quote!(i64)),
        (Some("U64"), _) => Ok(parse_quote!(u64)),
        (Some("Bool"), _) => Ok(parse_quote!(bool)),
        (Some("I32"), _) => Ok(parse_quote!(I32)),
        (Some("U16"), true) => Ok(parse_quote!(u16)),
        (Some("Usize"), _) => Ok(parse_quote!(Usize)),
        (Some("AbiResult"), _) => Ok(parse_quote!(AbiResult)),
        (Some("ByteSlice"), true) => Ok(parse_quote!(&[u8])),
        (Some("ByteVec"), false) => Ok(parse_quote!(Vec<u8>)),
        (Some("CStringResult"), false) => {
            Ok(parse_quote!(std::result::Result<CString, std::ffi::NulError>))
        }
        (Some("Never"), false) => Ok(parse_quote!(!)),
        (Some("sockaddr_in"), false) => Ok(parse_quote!(sockaddr_in)),
        (Some("Utf8"), true) => Ok(parse_quote!(Utf8<'_>)),
        (Some("IoResult"), false) => Ok(parse_quote!(IoResult)),
        _ => Err(invalid("unsupported native library type")),
    }
}

fn syscall_target(
    package: &Package,
    row: &Value,
    bindings: &CallBindings,
    target: Target<'_>,
) -> Result<(String, BTreeSet<ResolvedCall>)> {
    let (calls, resolved) = resolve_source("linux.syscalls", package, row, bindings, target)?;
    let Some(Call::Source {
        implementation,
        arity: 7,
        raw_abi: true,
    }) = calls.get("builtin::syscall")
    else {
        return Err(invalid("native syscall wrapper must pin builtin.syscall"));
    };
    // The unbound signal restorer traps if the syscall unexpectedly returns.
    let body = row["canonical_body"].as_str().unwrap();
    let restorer = body.trim() == "{\n    builtin::syscall(15); builtin::trap()\n}";
    if restorer {
        let Some(Call::Source {
            arity: 0,
            raw_abi: false,
            ..
        }) = calls.get("builtin::trap")
        else {
            return Err(invalid("signal restorer must pin builtin.trap"));
        };
        if calls.len() != 2 {
            return Err(invalid(
                "signal restorer must pin builtin.syscall and builtin.trap",
            ));
        }
    } else if calls.len() != 1 {
        return Err(invalid(
            "native syscall wrapper must pin only builtin.syscall",
        ));
    }
    Ok((implementation.clone(), resolved))
}

pub(super) fn lower(
    package_name: &str,
    package: &Package,
    exports: &BTreeMap<String, String>,
    bindings: &CallBindings,
    target: Target<'_>,
) -> Result<Output> {
    if exports.is_empty() {
        return Err(invalid("package has no public bindings"));
    }
    let main_name = format!("{package_name}.main");
    let main = exports.get(&main_name);
    let mut source = String::new();
    let mut main_wrapper = TokenStream::new();
    let mut requirements = RuntimeRequirements::default();
    let mut reachable = BTreeMap::new();
    let mut pending = BTreeSet::new();
    let mut symbols = BTreeMap::new();
    let mut resolved_calls = BTreeMap::new();
    let mut emitted = BTreeSet::new();
    let mut public_sources = BTreeSet::new();
    let mut checked_arithmetic = false;
    let mut emitted_syscalls = BTreeSet::new();
    for (export, implementation) in exports {
        let row = &package.tables["functions"][implementation];
        let signature = package.function_signature(row).map_err(validation)?.typed;
        if export == &main_name {
            let (body, resolved) = lower_body(
                package,
                row,
                bindings,
                target,
                &mut reachable,
                &mut pending,
                &mut requirements,
            )?;
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
                    requirements.requires_std = true;
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
                }
                .to_string(),
            );
            main_wrapper = quote!(fn main() { std::process::exit(llmlang_main(#arguments)); });
        } else if is_syscall_wrapper(package_name, row) {
            let (_, name) = export
                .rsplit_once('.')
                .ok_or_else(|| invalid("missing native namespace"))?;
            let call = native_call(name, package, row)?;
            let symbol = call.symbol();
            symbols.insert(export, symbol.to_string());
            reachable.insert(symbol, call);
        } else {
            symbols.insert(export, source_symbol(implementation).to_string());
            pending.insert(implementation.clone());
            public_sources.insert(implementation.clone());
        }
    }
    while !reachable.is_empty() || !pending.is_empty() {
        if let Some((name, call)) = reachable.pop_first() {
            if !emitted_syscalls.insert(name.clone()) {
                continue;
            }
            let row = &package.tables["functions"][&call.implementation];
            let (implementation, resolved) = syscall_target(package, row, bindings, target)?;
            let target = source_symbol(&implementation);
            pending.insert(implementation);
            resolved_calls.insert(call.implementation, resolved);
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
        let (body, resolved) = lower_body(
            package,
            row,
            bindings,
            target,
            &mut reachable,
            &mut pending,
            &mut requirements,
        )?;
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
        let mut result = library_type(&signature["result"], false)?;
        if super::scalar_source::supported_signature(package, row) {
            checked_arithmetic = true;
            result = parse_quote!(core::result::Result<#result, LlmlangError>);
        }
        if matches!(
            signature["result"].as_str(),
            Some("ByteVec" | "CStringResult")
        ) {
            requirements.requires_std = true;
        }
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
    let freestanding = main.is_some() && requirements.freestanding();
    let mut translation_unit = String::new();
    if freestanding {
        translation_unit.push_str("#![no_std]\n#![no_main]\n");
    }
    translation_unit.push_str(include_str!("native_runtime.rs"));
    if freestanding {
        translation_unit.push_str(include_str!("native_start.rs"));
    } else {
        translation_unit.push_str(include_str!("native_runtime_std.rs"));
        translation_unit.push_str(&main_wrapper.to_string());
    }
    if checked_arithmetic {
        translation_unit.push_str(
            &quote! {
                #[derive(Debug, PartialEq, Eq)]
                pub enum LlmlangError { ArithmeticOverflow, DivisionByZero, InvalidInput }
            }
            .to_string(),
        );
    }
    translation_unit.push_str(&source);
    Ok(Output {
        source: translation_unit,
        executable: main.is_some(),
        freestanding,
        exports: json!(symbols),
        calls: resolved_calls,
    })
}

pub(super) fn compile(output: &Output, artifact: &Path) -> Result<()> {
    let directory = tempfile::tempdir()?;
    let source = directory.path().join("package.rs");
    fs::write(&source, &output.source)?;
    let mut compiler = Command::new(std::env::var_os("RUSTC").unwrap_or_else(|| "rustc".into()));
    compiler.current_dir(directory.path()).args([
        "--edition=2021",
        "--target",
        "x86_64-unknown-linux-gnu",
        "--crate-name",
        "llmlang_native",
        "--crate-type",
        if output.executable { "bin" } else { "rlib" },
        "-C",
        "overflow-checks=yes",
    ]);
    if output.executable {
        compiler.args(["-C", "debuginfo=2"]);
    }
    if output.freestanding {
        compiler.args([
            "-C",
            "panic=abort",
            "-C",
            "opt-level=s",
            "-C",
            "relocation-model=static",
            "-C",
            "link-arg=-nostartfiles",
            "-C",
            "link-arg=-static",
        ]);
    }
    run_build_tool(compiler.arg("-o").arg(artifact).arg(&source))
}

fn run_build_tool(command: &mut Command) -> Result<()> {
    let program = command.get_program().to_string_lossy().into_owned();
    let result = command
        .output()
        .map_err(|error| ServerError::new("BuildFailed", format!("{program}: {error}")))?;
    if !result.status.success() {
        return Err(ServerError::new(
            "BuildFailed",
            format!(
                "{program}: {}",
                String::from_utf8_lossy(&result.stderr).trim()
            ),
        ));
    }
    Ok(())
}

pub(super) fn split_debug(artifact: &Path, name: &str) -> Result<PathBuf> {
    let objcopy = std::env::var_os("OBJCOPY").unwrap_or_else(|| "objcopy".into());
    let extracted = artifact.with_extension("debug");
    run_build_tool(
        Command::new(&objcopy)
            .arg("--only-keep-debug")
            .arg(artifact)
            .arg(&extracted),
    )?;
    let digest = Sha256::digest(fs::read(&extracted)?);
    let debug = artifact.with_file_name(format!("{name}.{digest:x}.debug"));
    fs::rename(extracted, &debug)?;
    let mut debuglink = OsString::from("--add-gnu-debuglink=");
    debuglink.push(&debug);
    run_build_tool(
        Command::new(&objcopy)
            .arg("--strip-all")
            .arg(debuglink)
            .arg(artifact),
    )?;
    Ok(debug)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn selects_bindings_by_specificity_and_reports_overlapping_partial_matches() {
        let mut binding = InterfaceBinding {
            pin: InterfacePin {
                name: "example.write".into(),
                version_hash: "version".into(),
                interface_hash: "interface".into(),
                required_contract_hash: "contract".into(),
            },
            version: "1".into(),
            implementations: BTreeMap::new(),
        };
        for (arch, os, implementation) in [
            ("", "", "portable"),
            ("x86_64", "", "architecture-only"),
            ("", "linux", "os-only"),
            ("x86_64", "linux", "exact"),
            ("aarch64", "ios", "device"),
            ("aarch64", "ios-simulator", "simulator"),
        ] {
            binding
                .implementations
                .entry(arch.into())
                .or_default()
                .insert(os.into(), implementation.into());
        }
        for (target, selected) in [
            (LINUX_X86_64, (LINUX_X86_64, "exact")),
            (("x86_64", "windows"), (("x86_64", ""), "architecture-only")),
            (("i686", "linux"), (("", "linux"), "os-only")),
            (("aarch64", "android"), (("", ""), "portable")),
            (("aarch64", "ios"), (("aarch64", "ios"), "device")),
            (
                ("aarch64", "ios-simulator"),
                (("aarch64", "ios-simulator"), "simulator"),
            ),
        ] {
            assert_eq!(binding.select(target).unwrap(), selected);
        }
        binding
            .implementations
            .get_mut("x86_64")
            .unwrap()
            .remove("linux");
        let error = binding.select(LINUX_X86_64).unwrap_err();
        assert_eq!(error.code, "AmbiguousBinding");
        assert!(error
            .message
            .contains(r#"("x86_64", "") and ("", "linux")"#));
    }

    #[test]
    fn builtin_references_ignore_comments_and_literals() {
        assert_eq!(
            referenced_builtin(r#"{ /* builtin__trap() */ let name = "builtin__trap"; }"#).unwrap(),
            None,
        );
        assert_eq!(
            referenced_builtin("{ wrapper::<u32>(qualified::r#builtin__size_of::<u32>()); }")
                .unwrap()
                .as_deref(),
            Some("builtin__size_of"),
        );
    }
}
