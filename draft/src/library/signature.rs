//! Canonical function signature text and its language-versioned identity.

use super::{invalid, Manifest, Package, Result};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::BTreeSet;

const SCALAR: &str = "scalar-v1";

/// A canonical signature decoded to ordered typed parameters and result.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FunctionSignature {
    pub typed: Value,
}

/// Render canonical signature text for a resolved signature.
pub fn function_signature_text(typed: &Value) -> Result<String> {
    let fields = typed
        .as_object()
        .filter(|fields| fields.len() == 2)
        .ok_or_else(|| invalid("expected ordered parameters and a function result"))?;
    let parameters = fields
        .get("parameters")
        .and_then(Value::as_array)
        .ok_or_else(|| invalid("function signature parameters must be ordered"))?;
    let result = fields
        .get("result")
        .ok_or_else(|| invalid("missing function result"))?;
    let mut names = BTreeSet::new();
    let mut entries = Vec::new();
    for parameter in parameters {
        let fields = parameter
            .as_object()
            .filter(|fields| fields.len() == 2)
            .ok_or_else(|| invalid("expected parameter name and type"))?;
        let name = fields
            .get("name")
            .and_then(Value::as_str)
            .filter(|name| identifier(name))
            .ok_or_else(|| invalid("invalid parameter name"))?;
        let kind = fields
            .get("type")
            .ok_or_else(|| invalid("missing parameter type"))?;
        if !names.insert(name) {
            return Err(invalid("duplicate function parameter"));
        }
        entries.push(format!("{name}: {}", type_text(kind)?));
    }
    Ok(format!(
        "({}) -> {}",
        entries.join(", "),
        type_text(result)?
    ))
}

fn identifier(value: &str) -> bool {
    let mut chars = value.bytes();
    chars
        .next()
        .is_some_and(|b| b.is_ascii_alphabetic() || b == b'_')
        && chars.all(|b| b.is_ascii_alphanumeric() || b == b'_')
}

fn bare_type(value: &str) -> bool {
    value
        .as_bytes()
        .first()
        .is_some_and(|byte| byte.is_ascii_alphabetic() || *byte == b'_')
        && value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || b"_.:<>-".contains(&byte))
}

fn type_text(kind: &Value) -> Result<String> {
    if let Some(name) = kind.as_str().filter(|name| bare_type(name)) {
        return Ok(name.into());
    }
    if !kind.is_object() && !kind.is_array() && kind.as_str().is_none_or(str::is_empty) {
        return Err(invalid("invalid function type"));
    }
    let mut bytes = Vec::new();
    super::record::canonical_json(kind, &mut bytes)?;
    Ok(String::from_utf8(bytes).expect("JSON is UTF-8"))
}

fn read_type(input: &mut &str) -> Result<Value> {
    if input.starts_with(['{', '[', '"']) {
        let mut value = serde_json::Deserializer::from_str(input).into_iter::<Value>();
        let decoded = value
            .next()
            .transpose()?
            .ok_or_else(|| invalid("missing function type"))?;
        *input = &input[value.byte_offset()..];
        return Ok(decoded);
    }
    let end = input.find([',', ')']).unwrap_or(input.len());
    let (kind, rest) = input.split_at(end);
    if !bare_type(kind) {
        return Err(invalid("invalid function type"));
    }
    *input = rest;
    Ok(json!(kind))
}

/// Parse canonical signature text under its owning package language definition.
pub fn parse_function_signature(manifest: &Manifest, text: &str) -> Result<FunctionSignature> {
    super::check_manifest(manifest, &[super::LANGUAGE_VERSION])?;
    let mut input = text
        .strip_prefix('(')
        .ok_or_else(|| invalid("function signature requires a parameter list"))?;
    let mut parameters = Vec::new();
    if !input.starts_with(')') {
        loop {
            let (name, rest) = input
                .split_once(": ")
                .ok_or_else(|| invalid("missing parameter type"))?;
            input = rest;
            let kind = read_type(&mut input)?;
            parameters.push(json!({"name": name, "type": kind}));
            match input.strip_prefix(", ") {
                Some(rest) => input = rest,
                None => break,
            }
        }
    }
    input = input
        .strip_prefix(") -> ")
        .ok_or_else(|| invalid("missing function result"))?;
    let result = read_type(&mut input)?;
    let typed = json!({"parameters": parameters, "result": result});
    if !input.is_empty() || function_signature_text(&typed)? != text {
        return Err(invalid("noncanonical function signature text"));
    }
    Ok(FunctionSignature { typed })
}

impl FunctionSignature {
    /// Convert the common typed signature to the scalar verifier's input shape.
    pub fn into_scalar(mut self) -> Result<Self> {
        fn scalar_type(value: &Value) -> Result<&str> {
            match value.as_str() {
                Some("I64") => Ok("i64"),
                Some("Bool") => Ok("bool"),
                _ => Err(invalid("unsupported scalar signature type")),
            }
        }
        let parameters = self.typed["parameters"]
            .as_array()
            .ok_or_else(|| invalid("missing signature parameters"))?
            .iter()
            .map(|parameter| Ok(json!([parameter["name"], scalar_type(&parameter["type"])?])))
            .collect::<Result<Vec<_>>>()?;
        self.typed = json!({"params": parameters, "result": scalar_type(&self.typed["result"])?});
        Ok(self)
    }
}

fn digest(manifest: &Manifest, text: &str) -> String {
    let mut digest = Sha256::new();
    digest.update(b"llmlang-function-signature/v2\0");
    digest.update(manifest.language_version.as_bytes());
    digest.update(b"\0");
    digest.update(manifest.language_component_registry_digest.as_bytes());
    digest.update(b"\0");
    digest.update(text.as_bytes());
    format!("sha256:{:x}", digest.finalize())
}

/// Parse the signature and verify its identity under the owning manifest.
pub fn resolve_function_signature(
    manifest: &Manifest,
    hash: &str,
    text: &str,
) -> Result<FunctionSignature> {
    let signature = parse_function_signature(manifest, text)?;
    if digest(manifest, text) != hash {
        return Err(invalid("function signature hash mismatch"));
    }
    Ok(signature)
}

impl Package {
    /// Stage a content-addressed signature, sharing rows across implementations.
    pub fn stage_function_signature(&mut self, typed: &Value) -> Result<String> {
        super::check_manifest(&self.manifest, &[super::LANGUAGE_VERSION])?;
        let text = function_signature_text(typed)?;
        let hash = digest(&self.manifest, &text);
        let rows = self
            .tables
            .get_mut("function_signatures")
            .expect("signature table");
        let row = json!({"function_signature_hash": hash, "function_signature_content": text});
        let stored = rows.entry(hash.clone()).or_insert_with(|| row.clone());
        if stored != &row {
            return Err(invalid("conflicting function signature content"));
        }
        Ok(hash)
    }

    /// Resolve a function row using tables from the package and loaded dependencies.
    pub fn function_signature(&self, function: &Value) -> Result<FunctionSignature> {
        let hash = function["function_signature_hash"]
            .as_str()
            .ok_or_else(|| invalid("missing function signature hash"))?;
        let row = self.tables["function_signatures"]
            .get(hash)
            .ok_or_else(|| invalid(format!("unresolved function signature {hash}")))?;
        let text = row["function_signature_content"]
            .as_str()
            .ok_or_else(|| invalid("missing function signature content"))?;
        let signature = resolve_function_signature(&self.manifest, hash, text)?;
        let profile = function["provided_contract_hash"]
            .as_str()
            .and_then(|key| self.tables["contracts"].get(key))
            .and_then(|contract| contract["profile"].as_str());
        if profile == Some(SCALAR) {
            signature.into_scalar()
        } else {
            Ok(signature)
        }
    }
}

pub(crate) fn validate_block(source: &str) -> Result<()> {
    use proc_macro2::{Delimiter, TokenStream, TokenTree};

    let mut tokens = source
        .parse::<TokenStream>()
        .map_err(|error| invalid(format!("invalid function body text: {error}")))?
        .into_iter();
    if !matches!(tokens.next(), Some(TokenTree::Group(block)) if block.delimiter() == Delimiter::Brace)
        || tokens.next().is_some()
    {
        return Err(invalid("expected a body-only block"));
    }
    Ok(())
}
