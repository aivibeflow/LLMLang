//! Derive unchecked call compatibility obligations from resolved calls.

use super::{hash, validation, Package, Result};
use serde::Serialize;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize)]
pub(super) struct ResolvedCall {
    pub callee_impl_hash: String,
    pub required_contract_hash: String,
}

pub(super) type CallsByCaller = BTreeMap<String, BTreeSet<ResolvedCall>>;

pub(super) fn from_ir(package: &Package) -> CallsByCaller {
    let mut result = BTreeMap::new();
    for (caller, row) in &package.tables["functions"] {
        let mut calls = BTreeSet::new();
        collect_pins(&row["canonical_body"], &mut calls);
        if !calls.is_empty() {
            result.insert(caller.clone(), calls);
        }
    }
    result
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
            let context = json!({
                "language_version": package.manifest.language_version,
                "profile": profile,
                "dependencies": package.manifest.dependencies,
                "caller_provided_contract_hash": caller_provided,
                "callee_provided_contract_hash": provided,
            });
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
