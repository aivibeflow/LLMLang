//! Resolve failed obligations against the exact SPG used for verification.

use super::{Package, Result, ServerError};
use serde_json::{json, Value};

pub(super) fn failures(package: &Package, report: &Value) -> Result<Vec<Value>> {
    let mut failures = Vec::new();
    for check in report["checks"].as_array().into_iter().flatten() {
        let alias = field(check, "function")?;
        let identity = &report["identities"][alias];
        for (role, pin) in [
            ("public_or_required", "required_or_public_contract_hash"),
            ("provided", "provided_contract_hash"),
        ] {
            let domain = if role == "provided" {
                "provided"
            } else {
                "public"
            };
            let evidence = &check["domains"][domain];
            if evidence["status"] == "empty" {
                failures.push(resolved_failure(
                    package,
                    report,
                    identity,
                    "empty-domain",
                    role,
                    field(identity, pin)?,
                    evidence,
                )?);
            }
        }
        for obligation in ["body_counterexamples", "refinement_counterexamples"] {
            for evidence in check[obligation].as_array().into_iter().flatten() {
                if !matches!(
                    evidence["status"].as_str(),
                    Some("confirmed-source" | "confirmed-contract")
                ) {
                    continue;
                }
                let kind = field(evidence, "kind")?;
                let (role, failed_contract, comparison, callee) = match kind {
                    "body-postcondition" => (
                        "provided",
                        field(identity, "provided_contract_hash")?,
                        None,
                        None,
                    ),
                    "provider-precondition" => (
                        "provided",
                        field(identity, "provided_contract_hash")?,
                        Some(field(identity, "required_or_public_contract_hash")?),
                        None,
                    ),
                    "provider-guarantee" => (
                        "public_or_required",
                        field(identity, "required_or_public_contract_hash")?,
                        Some(field(identity, "provided_contract_hash")?),
                        None,
                    ),
                    "callee-precondition" => {
                        let alias = field(&evidence["invalid_call"], "callee")?;
                        let callee = &report["identities"][alias];
                        (
                            "required",
                            field(callee, "required_or_public_contract_hash")?,
                            None,
                            Some(callee),
                        )
                    }
                    _ => continue,
                };
                let mut failure = resolved_failure(
                    package,
                    report,
                    identity,
                    kind,
                    role,
                    failed_contract,
                    evidence,
                )?;
                if let Some(hash) = comparison {
                    failure["comparison_contract"] = contract(package, report, hash)?;
                }
                if let Some(callee) = callee {
                    failure["callee"] = function(package, report, callee)?;
                }
                failures.push(failure);
            }
        }
    }
    Ok(failures)
}

fn resolved_failure(
    package: &Package,
    report: &Value,
    identity: &Value,
    kind: &str,
    role: &str,
    failed_contract: &str,
    evidence: &Value,
) -> Result<Value> {
    Ok(json!({
        "kind": kind, "contract_role": role,
        "function": function(package, report, identity)?,
        "contract": contract(package, report, failed_contract)?,
        "evidence": evidence,
    }))
}

fn field<'a>(row: &'a Value, name: &str) -> Result<&'a str> {
    row[name]
        .as_str()
        .ok_or_else(|| ServerError::new("ToolError", format!("verification report lacks {name}")))
}

fn row<'a>(package: &'a Package, table: &str, hash: &str) -> Result<&'a Value> {
    package.tables[table].get(hash).ok_or_else(|| {
        ServerError::new(
            "ToolError",
            format!("verification refers to absent {table}/{hash}"),
        )
    })
}

fn function(package: &Package, report: &Value, identity: &Value) -> Result<Value> {
    let hash = field(identity, "implementation_hash")?;
    let mut resolved = row(package, "functions", hash)?.clone();
    let signature = field(&resolved, "function_signature_hash")?;
    let mut signature = row(package, "function_signatures", signature)?.clone();
    signature["typed_signature"] = package
        .function_signature(&resolved)
        .map_err(super::validation)?
        .typed;
    let provided = field(&resolved, "provided_contract_hash")?;
    resolved["provided_contract"] = contract(package, report, provided)?;
    resolved["function_signature"] = signature;
    Ok(resolved)
}

fn contract(package: &Package, report: &Value, hash: &str) -> Result<Value> {
    let mut resolved = row(package, "contracts", hash)?.clone();
    resolved["rules"] = json!(package.tables["contract_rules"]
        .values()
        .filter(|rule| rule["contract_hash"] == hash)
        .collect::<Vec<_>>());
    if let Some(ir) = report["contract_ir"].get(hash) {
        resolved["ir"] = ir.clone();
    }
    Ok(resolved)
}
