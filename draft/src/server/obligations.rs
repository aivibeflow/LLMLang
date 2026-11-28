//! Derive unchecked call compatibility obligations from resolved calls.

use super::{hash, scalar_source, validation, Package, Result};
use serde::Serialize;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize)]
pub(super) struct ResolvedCall {
    pub callee_impl_hash: String,
    pub required_contract_hash: String,
    pub binding: Option<ResolvedBinding>,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize)]
pub(super) struct ResolvedBinding {
    pub target_arch: String,
    pub target_os: String,
    pub binding_arch: String,
    pub binding_os: String,
    pub interface: super::native::InterfacePin,
}

pub(super) type CallsByCaller = BTreeMap<String, BTreeSet<ResolvedCall>>;

pub(super) fn from_ir(package: &Package) -> Result<CallsByCaller> {
    let mut result = BTreeMap::new();
    for (caller, row) in &package.tables["functions"] {
        let mut calls = BTreeSet::new();
        let body = scalar_source::body(package, row)?;
        collect_pins(&body, &mut calls);
        if !calls.is_empty() {
            result.insert(caller.clone(), calls);
        }
    }
    Ok(result)
}

fn collect_pins(value: &Value, calls: &mut BTreeSet<ResolvedCall>) {
    match value {
        Value::Object(fields) => {
            if let (Some(callee), Some(required)) = (
                fields.get("callee_impl_hash").and_then(Value::as_str),
                fields.get("required_contract_hash").and_then(Value::as_str),
            ) {
                calls.insert(ResolvedCall {
                    callee_impl_hash: callee.into(),
                    required_contract_hash: required.into(),
                    binding: None,
                });
            }
            for child in fields.values() {
                collect_pins(child, calls);
            }
        }
        Value::Array(items) => {
            for item in items {
                collect_pins(item, calls);
            }
        }
        _ => {}
    }
}

pub(super) fn rows(package: &Package, calls: &CallsByCaller) -> Result<BTreeMap<String, Value>> {
    let mut rows = BTreeMap::new();
    for (caller, calls) in calls {
        let caller_provided = package.tables["functions"]
            .get(caller)
            .and_then(|row| row["provided_contract_hash"].as_str())
            .ok_or_else(|| validation("missing caller contract"))?;
        let profile = package.tables["contracts"]
            .get(caller_provided)
            .and_then(|row| row["profile"].as_str())
            .ok_or_else(|| validation("missing caller profile"))?;
        for call in calls {
            let callee = &call.callee_impl_hash;
            let required = &call.required_contract_hash;
            let provided = package.tables["functions"]
                .get(callee)
                .and_then(|row| row["provided_contract_hash"].as_str())
                .ok_or_else(|| validation("missing callee contract"))?;
            if !package.tables["contracts"].contains_key(required)
                || !package.tables["contracts"].contains_key(provided)
            {
                return Err(validation("unresolved call contract"));
            }
            let mut context = json!({
                "language_version": package.manifest.language_version,
                "language_component_registry_digest": package.manifest.language_component_registry_digest,
                "profile": profile,
                "caller_provided_contract_hash": caller_provided,
                "callee_provided_contract_hash": provided,
            });
            if let Some(binding) = &call.binding {
                context["binding"] = json!(binding);
            } else {
                context["dependencies"] = json!(package.manifest.dependencies);
            }
            let context_hash = format!(
                "sha256:{}",
                hash(&("llmlang-verification-context/v1", context))?
            );
            let mut row = json!({
                "kind": "call_compatibility",
                "caller_impl_hash": caller,
                "callee_impl_hash": callee,
                "caller_required_contract_hash": required,
                "verification_context_hash": context_hash,
            });
            let id = format!(
                "sha256:{}",
                hash(&("llmlang-verification-obligation/v1", &row))?
            );
            row["obligation_hash"] = json!(id);
            rows.insert(id, row);
        }
    }
    Ok(rows)
}

pub(super) fn replace(package: &mut Package, expected: BTreeMap<String, Value>) {
    let obligations = package.tables.get_mut("verification_obligations").unwrap();
    obligations.retain(|_, row| row["kind"] != "call_compatibility");
    obligations.extend(expected);
    let active: BTreeSet<_> = obligations.keys().cloned().collect();
    package
        .tables
        .get_mut("verification_runs")
        .unwrap()
        .retain(|_, run| {
            run["obligation_hash"]
                .as_str()
                .is_some_and(|hash| active.contains(hash))
        });
}
