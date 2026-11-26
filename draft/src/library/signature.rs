//! Canonical function signature text and its profile-specific identity.

use super::{invalid, Package, Result};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::BTreeSet;

const SCALAR: &str = "scalar-v1";

/// A verified signature decoded back to the typed representation of its profile.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FunctionSignature {
    pub profile: String,
    pub typed: Value,
}

/// Render the v4 canonical signature text for a resolved signature.
pub fn function_signature_text(profile: &str, typed: &Value) -> Result<String> {
    if profile.is_empty()
        || !profile
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b"._-".contains(&b))
    {
        return Err(invalid("invalid function signature profile"));
    }
    let parameter_key = if profile == SCALAR {
        "params"
    } else {
        "parameters"
    };
    let fields = typed
        .as_object()
        .filter(|fields| fields.len() == 2)
        .ok_or_else(|| invalid("expected ordered parameters and a function result"))?;
    let parameters = fields
        .get(parameter_key)
        .and_then(Value::as_array)
        .ok_or_else(|| invalid("function signature parameters must be ordered"))?;
    let result = fields
        .get("result")
        .ok_or_else(|| invalid("missing function result"))?;
    let mut names = BTreeSet::new();
    let mut entries = Vec::new();
    for parameter in parameters {
        let (name, kind) = if profile == SCALAR {
            let pair = parameter
                .as_array()
                .filter(|pair| pair.len() == 2)
                .ok_or_else(|| invalid("expected scalar parameter name and type"))?;
            (pair[0].as_str(), &pair[1])
        } else {
            let fields = parameter
                .as_object()
                .filter(|fields| fields.len() == 2)
                .ok_or_else(|| invalid("expected native parameter name and type"))?;
            (
                fields.get("name").and_then(Value::as_str),
                fields
                    .get("type")
                    .ok_or_else(|| invalid("missing parameter type"))?,
            )
        };
        let name = name
            .filter(|name| identifier(name))
            .ok_or_else(|| invalid("invalid parameter name"))?;
        if !names.insert(name) {
            return Err(invalid("duplicate function parameter"));
        }
        entries.push(format!("{name}: {}", type_text(profile, kind)?));
    }
    Ok(format!(
        "{profile} ({}) -> {}",
        entries.join(", "),
        type_text(profile, result)?
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

fn type_text(profile: &str, kind: &Value) -> Result<String> {
    if profile == SCALAR {
        return match kind.as_str() {
            Some("i64") => Ok("I64".into()),
            Some("bool") => Ok("Bool".into()),
            _ => Err(invalid("unsupported scalar function type")),
        };
    }
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

fn read_type(profile: &str, input: &mut &str) -> Result<Value> {
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
    if profile == SCALAR {
        return match kind {
            "I64" => Ok(json!("i64")),
            "Bool" => Ok(json!("bool")),
            _ => Err(invalid("unsupported scalar signature type")),
        };
    }
    Ok(json!(kind))
}

fn parse(text: &str) -> Result<FunctionSignature> {
    let (profile, mut input) = text
        .split_once(" (")
        .ok_or_else(|| invalid("function signature requires a profile and parameter list"))?;
    let mut params = Vec::new();
    if !input.starts_with(')') {
        loop {
            let (name, rest) = input
                .split_once(": ")
                .ok_or_else(|| invalid("missing parameter type"))?;
            input = rest;
            let kind = read_type(profile, &mut input)?;
            params.push(if profile == SCALAR {
                json!([name, kind])
            } else {
                json!({"name": name, "type": kind})
            });
            match input.strip_prefix(", ") {
                Some(rest) => input = rest,
                None => break,
            }
        }
    }
    input = input
        .strip_prefix(") -> ")
        .ok_or_else(|| invalid("missing function result"))?;
    let result = read_type(profile, &mut input)?;
    let parameter_key = if profile == SCALAR {
        "params"
    } else {
        "parameters"
    };
    let typed = json!({parameter_key: params, "result": result});
    if !input.is_empty() || function_signature_text(profile, &typed)? != text {
        return Err(invalid("noncanonical function signature text"));
    }
    Ok(FunctionSignature {
        profile: profile.into(),
        typed,
    })
}

fn digest(profile: &str, text: &str) -> String {
    let mut digest = Sha256::new();
    digest.update(b"llmlang-function-signature/v1\0");
    digest.update(profile.as_bytes());
    digest.update(b"\0");
    digest.update(text.as_bytes());
    format!("sha256:{:x}", digest.finalize())
}

/// Parse the signature and verify its exact identity, including the profile.
pub fn resolve_function_signature(hash: &str, text: &str) -> Result<FunctionSignature> {
    let signature = parse(text)?;
    if digest(&signature.profile, text) != hash {
        return Err(invalid("function signature hash mismatch"));
    }
    Ok(signature)
}

impl Package {
    /// Stage a content-addressed signature, sharing rows across implementations.
    pub fn stage_function_signature(&mut self, profile: &str, typed: &Value) -> Result<String> {
        let text = function_signature_text(profile, typed)?;
        let hash = digest(profile, &text);
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
        let signature = resolve_function_signature(hash, text)?;
        if let Some(contract) = function["provided_contract_hash"]
            .as_str()
            .and_then(|key| self.tables["contracts"].get(key))
        {
            if contract["profile"] != signature.profile {
                return Err(invalid("function signature and contract profiles disagree"));
            }
        }
        Ok(signature)
    }
}

pub(crate) fn validate_body(body: &Value) -> Result<()> {
    match body {
        Value::String(source) => validate_block(source),
        Value::Array(_) => Ok(()),
        Value::Object(fields)
            if ![
                "signature",
                "typed_signature",
                "parameters",
                "params",
                "result",
                "function_signature_hash",
            ]
            .iter()
            .any(|key| fields.contains_key(*key)) =>
        {
            if let Some(source) = fields.get("source") {
                validate_block(
                    source
                        .as_str()
                        .ok_or_else(|| invalid("expected body source text"))?,
                )?;
            }
            Ok(())
        }
        _ => Err(invalid("canonical body must contain only body IR")),
    }
}

fn validate_block(source: &str) -> Result<()> {
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
