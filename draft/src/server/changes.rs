//! Typed changes and their canonical identities for the scalar authoring profile.
use crate::ServerError;
use llmlang_spg::{content_hash, Package};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};

type Result<T> = std::result::Result<T, ServerError>;
const SCALAR_PROFILE: &str = "scalar-v1";

#[derive(Clone, Debug, Default, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct Selection {
    pub version: Option<String>,
    pub entry_point: Option<String>,
}

#[derive(Debug, Serialize)]
pub(crate) struct ChangeResult {
    pub identities: BTreeMap<String, String>,
    pub affected_functions: Vec<String>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(untagged, deny_unknown_fields)]
enum Reference {
    Hash(String),
    Local { local: String },
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "snake_case")]
enum Table {
    Contracts,
    Functions,
    Interfaces,
}

impl Table {
    fn table(self) -> &'static str {
        match self {
            Self::Contracts => "contracts",
            Self::Functions => "functions",
            Self::Interfaces => "interfaces",
        }
    }
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Rule {
    kind: RuleKind,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    error_label: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    predicate: Option<Value>,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
enum RuleKind {
    Requires,
    Ensures,
    ErrorDeclaration,
    ErrorGuard,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "op", rename_all = "snake_case", deny_unknown_fields)]
enum Operation {
    SetVersion {
        version: String,
        #[serde(deserialize_with = "Deserialize::deserialize")]
        expected_version: Option<String>,
    },
    PinDependency {
        name: String,
        snapshot_id: String,
        #[serde(deserialize_with = "Deserialize::deserialize")]
        expected_snapshot_id: Option<String>,
    },
    UnpinDependency {
        name: String,
        expected_snapshot_id: String,
    },
    PutContract {
        id: String,
        typed_signature: Value,
        rules: Vec<Rule>,
        #[serde(default)]
        user_request_texts: Vec<String>,
        previous: Option<String>,
        expected_hash: Option<String>,
    },
    PutFunction {
        id: String,
        typed_signature: Value,
        canonical_body: Value,
        provided_contract: Reference,
        previous: Option<String>,
        expected_hash: Option<String>,
    },
    PutInterface {
        id: String,
        name: String,
        public_contract: Reference,
        previous: Option<String>,
        expected_hash: Option<String>,
    },
    Bind {
        interface: Reference,
        implementation: Reference,
        #[serde(default)]
        arch: String,
        #[serde(default)]
        os: String,
        #[serde(deserialize_with = "Deserialize::deserialize")]
        expected_implementation: Option<String>,
    },
    Unbind {
        name: String,
        #[serde(default)]
        arch: String,
        #[serde(default)]
        os: String,
        expected_implementation: String,
    },
    SetEntryPoint {
        #[serde(deserialize_with = "Deserialize::deserialize")]
        implementation: Option<Reference>,
        #[serde(deserialize_with = "Deserialize::deserialize")]
        expected_implementation: Option<String>,
    },
    RemoveObject {
        table: Table,
        identity: String,
        expected_hash: String,
    },
}

type Exports = BTreeMap<(String, String, String), (String, String)>;

fn invalid(message: impl Into<String>) -> ServerError {
    ServerError::new("InvalidArguments", message)
}

fn conflict(message: impl Into<String>) -> ServerError {
    ServerError::new("Conflict", message)
}

fn missing(message: impl Into<String>) -> ServerError {
    ServerError::new("MissingReference", message)
}

fn require_text(value: &str, what: &str) -> Result<()> {
    if value.trim().is_empty() {
        return Err(invalid(format!("{what} must be nonempty")));
    }
    Ok(())
}

fn require_hash(value: &str, what: &str) -> Result<()> {
    if value.len() == 64
        && value
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
    {
        return Ok(());
    }
    Err(invalid(format!("{what} must be a lowercase SHA-256 hash")))
}

fn hash(domain: &str, value: &Value) -> Result<String> {
    content_hash(domain, value).map_err(|error| invalid(error.to_string()))
}

fn canonical_rule(rule: &Rule) -> Result<Value> {
    let label = rule.error_label.as_deref();
    if let Some(label) = label {
        require_text(label, "error label")?;
    }
    let predicate = rule.predicate.as_ref();
    let supported = predicate.is_some_and(|value| value.is_string() || value.is_boolean());
    match (rule.kind, label, predicate, supported) {
        (RuleKind::Requires | RuleKind::Ensures, None, Some(_), true)
        | (RuleKind::ErrorDeclaration, Some(_), None, _)
        | (RuleKind::ErrorGuard, Some(_), Some(_), true) => {}
        _ => {
            return Err(invalid(
                "rule kind does not match its predicate or error label",
            ))
        }
    }
    Ok(json!(rule))
}

fn rule_identity(rule: &Value) -> Result<String> {
    hash("llmlang-server-rule-v1", rule)
}

fn contract_identity<'a>(
    signature: &Value,
    rule_hashes: impl Iterator<Item = &'a String>,
) -> Result<String> {
    hash(
        "llmlang-server-contract-v1",
        &json!({"profile": SCALAR_PROFILE, "signature": signature, "rules": rule_hashes.collect::<Vec<_>>()}),
    )
}

fn function_identity(signature: &Value, body: &Value, provided: &str) -> Result<String> {
    hash(
        "llmlang-server-implementation-v1",
        &json!({"signature": signature, "body": body, "provided_contract_hash": provided}),
    )
}

fn interface_identity(name: &str, public: &str) -> Result<String> {
    hash(
        "llmlang-server-interface-v1",
        &json!({"name": name, "public_contract_hash": public}),
    )
}

fn version_identity(version: &str) -> Result<String> {
    hash("llmlang-server-version-v1", &json!({"version": version}))
}

pub(super) fn binding_identity(package: &Package, version_hash: &str) -> Result<String> {
    let rows: Vec<_> = package.tables["bindings"]
        .values()
        .filter(|row| row["version_hash"] == version_hash)
        .collect();
    Ok(format!(
        "sha256:{}",
        hash("llmlang-server-bindings-v3", &json!({"bindings": rows}))?
    ))
}

fn check_expected<T: PartialEq + std::fmt::Debug>(
    current: Option<&T>,
    expected: Option<&T>,
    what: &str,
) -> Result<()> {
    if current != expected {
        return Err(conflict(format!(
            "{what}: expected {expected:?}, found {current:?}"
        )));
    }
    Ok(())
}

fn row<'a>(package: &'a Package, table: Table, key: &str) -> Result<&'a Value> {
    package.tables[table.table()]
        .get(key)
        .ok_or_else(|| missing(format!("{} has no object {key}", table.table())))
}

fn check_edit(
    package: &Package,
    table: Table,
    previous: &Option<String>,
    expected: &Option<String>,
) -> Result<()> {
    match (previous, expected) {
        (None, None) => Ok(()),
        (Some(previous), Some(expected)) => {
            let actual = hash(previous, row(package, table, previous)?)?;
            check_expected(Some(&actual), Some(expected), "object hash")
        }
        _ => Err(invalid(
            "previous and expected_hash must be supplied together",
        )),
    }
}

fn insert_row(package: &mut Package, table: &str, key: &str, content: Value) -> Result<()> {
    let rows = package.tables.get_mut(table).expect("known table");
    if let Some(existing) = rows.get(key) {
        if existing != &content {
            return Err(conflict(format!("identity collision in {table} for {key}")));
        }
    } else {
        rows.insert(key.to_owned(), content);
    }
    Ok(())
}

fn string<'a>(value: &'a Value, field: &str) -> Result<&'a str> {
    value[field]
        .as_str()
        .ok_or_else(|| invalid(format!("missing string field {field}")))
}

fn exports(package: &Package) -> Result<Exports> {
    let mut exports = Exports::new();
    for binding in package.tables["bindings"].values() {
        let interface = string(binding, "interface_hash")?;
        let name = string(row(package, Table::Interfaces, interface)?, "name")?;
        let arch = string(binding, "arch")?;
        let os = string(binding, "os")?;
        let implementation = string(binding, "impl_hash")?;
        if exports
            .insert(
                (name.into(), arch.into(), os.into()),
                (interface.to_string(), implementation.to_string()),
            )
            .is_some()
        {
            return Err(conflict(format!(
                "duplicate export {name} for ({arch:?}, {os:?})"
            )));
        }
    }
    Ok(exports)
}

fn write_selection(package: &mut Package, selection: &Selection, exports: &Exports) -> Result<()> {
    package
        .tables
        .get_mut("versions")
        .expect("version table")
        .clear();
    package
        .tables
        .get_mut("bindings")
        .expect("binding table")
        .clear();
    if let Some(version) = &selection.version {
        let version_hash = version_identity(version)?;
        for ((_, arch, os), (interface, implementation)) in exports {
            let key = format!("{version_hash}:{interface}:{arch}:{os}");
            insert_row(
                package,
                "bindings",
                &key,
                json!({"version_hash":version_hash,"interface_hash":interface,"arch":arch,"os":os,"impl_hash":implementation}),
            )?;
        }
        let binding_hash = binding_identity(package, &version_hash)?;
        insert_row(
            package,
            "versions",
            &version_hash,
            json!({"version_hash": version_hash, "version": version, "binding_hash": binding_hash}),
        )?;
    } else if !exports.is_empty() || selection.entry_point.is_some() {
        return Err(invalid(
            "set a package version before selecting exports or an entry point",
        ));
    }
    Ok(())
}

fn local_id(operation: &Operation) -> Option<(&str, Table)> {
    match operation {
        Operation::PutContract { id, .. } => Some((id, Table::Contracts)),
        Operation::PutFunction { id, .. } => Some((id, Table::Functions)),
        Operation::PutInterface { id, .. } => Some((id, Table::Interfaces)),
        _ => None,
    }
}

fn references_in_ir(node: &Value, name: &str, callback: &mut impl FnMut(&Value)) {
    match node {
        Value::Array(children) => {
            for child in children {
                references_in_ir(child, name, callback);
            }
        }
        Value::Object(fields) => {
            if let Some(pin) = fields.get(name) {
                callback(pin);
            }
            for (key, child) in fields {
                if key != name {
                    references_in_ir(child, name, callback);
                }
            }
        }
        _ => {}
    }
}

fn local_references(operation: &Operation) -> Result<Vec<(&str, Table)>> {
    fn push<'a>(reference: &'a Reference, table: Table, refs: &mut Vec<(&'a str, Table)>) {
        if let Reference::Local { local } = reference {
            refs.push((local, table));
        }
    }
    fn pins<'a>(node: &'a Value, refs: &mut Vec<(&'a str, Table)>) -> Result<()> {
        match node {
            Value::Array(children) => {
                for child in children {
                    pins(child, refs)?;
                }
            }
            Value::Object(fields) => {
                for (key, child) in fields {
                    let table = match key.as_str() {
                        "callee_impl_hash" => Table::Functions,
                        "required_contract_hash" => Table::Contracts,
                        _ => {
                            pins(child, refs)?;
                            continue;
                        }
                    };
                    match child {
                        Value::String(hash) => require_hash(hash, key)?,
                        Value::Object(reference) if reference.len() == 1 => {
                            let id = reference.get("local").and_then(Value::as_str).ok_or_else(
                                || invalid(format!("invalid local reference in {key}")),
                            )?;
                            refs.push((id, table));
                        }
                        _ => return Err(invalid(format!("invalid reference in {key}"))),
                    }
                }
            }
            _ => {}
        }
        Ok(())
    }

    let mut refs = Vec::new();
    match operation {
        Operation::PutFunction {
            canonical_body,
            provided_contract,
            ..
        } => {
            push(provided_contract, Table::Contracts, &mut refs);
            pins(canonical_body, &mut refs)?;
        }
        Operation::PutInterface {
            public_contract, ..
        } => push(public_contract, Table::Contracts, &mut refs),
        _ => {}
    }
    Ok(refs)
}

struct Locals {
    identities: BTreeMap<String, String>,
    kinds: BTreeMap<String, Table>,
}

impl Locals {
    fn resolve(&self, reference: &Reference, table: Table) -> Result<String> {
        match reference {
            Reference::Hash(key) => {
                require_hash(key, "reference")?;
                Ok(key.clone())
            }
            Reference::Local { local } => {
                if self.kinds.get(local) != Some(&table) {
                    return Err(missing(format!(
                        "local {local} does not identify a {}",
                        table.table()
                    )));
                }
                self.identities
                    .get(local)
                    .cloned()
                    .ok_or_else(|| missing(format!("unresolved local identity {local}")))
            }
        }
    }

    fn rewrite_ir(&self, value: &mut Value) -> Result<()> {
        match value {
            Value::Object(fields) => {
                for (key, child) in fields {
                    let table = match key.as_str() {
                        "callee_impl_hash" => Table::Functions,
                        "required_contract_hash" => Table::Contracts,
                        _ => {
                            self.rewrite_ir(child)?;
                            continue;
                        }
                    };
                    let reference = serde_json::from_value(child.clone())
                        .map_err(|e| invalid(e.to_string()))?;
                    *child = Value::String(self.resolve(&reference, table)?);
                }
            }
            Value::Array(children) => {
                for child in children {
                    self.rewrite_ir(child)?;
                }
            }
            _ => {}
        }
        Ok(())
    }
}

fn put(
    package: &mut Package,
    baseline: &Package,
    operation: &Operation,
    locals: &Locals,
) -> Result<String> {
    match operation {
        Operation::PutContract {
            typed_signature,
            rules,
            user_request_texts,
            previous,
            expected_hash,
            ..
        } => {
            check_edit(baseline, Table::Contracts, previous, expected_hash)?;
            let mut canonical = BTreeMap::new();
            for rule in rules {
                let content = canonical_rule(rule)?;
                let identity = rule_identity(&content)?;
                if canonical.insert(identity, content).is_some() {
                    return Err(invalid("duplicate contract rule"));
                }
            }
            let identity = contract_identity(typed_signature, canonical.keys())?;
            let mut texts: BTreeSet<_> = user_request_texts.iter().cloned().collect();
            let mut reviews = Vec::new();
            if let Some(existing) = package.tables["contracts"].get(&identity) {
                if let Some(stored) = existing["user_request_texts"].as_array() {
                    texts.extend(stored.iter().filter_map(Value::as_str).map(str::to_owned));
                }
                if let Some(stored) = existing["review_records"].as_array() {
                    reviews.clone_from(stored);
                }
            }
            let content = json!({
                "contract_hash": identity, "contract_kind": "function", "profile": SCALAR_PROFILE,
                "typed_signature": typed_signature, "user_request_texts": texts, "review_records": reviews
            });
            package
                .tables
                .get_mut("contracts")
                .expect("contract table")
                .insert(identity.clone(), content);
            for (rule_hash, mut content) in canonical {
                content["contract_hash"] = json!(identity);
                content["rule_hash"] = json!(rule_hash);
                insert_row(
                    package,
                    "contract_rules",
                    &format!("{identity}:{rule_hash}"),
                    content,
                )?;
            }
            Ok(identity)
        }
        Operation::PutFunction {
            typed_signature,
            canonical_body,
            provided_contract,
            previous,
            expected_hash,
            ..
        } => {
            check_edit(baseline, Table::Functions, previous, expected_hash)?;
            let provided = locals.resolve(provided_contract, Table::Contracts)?;
            let mut body = canonical_body.clone();
            locals.rewrite_ir(&mut body)?;
            let identity = function_identity(typed_signature, &body, &provided)?;
            let signature = package
                .stage_function_signature(SCALAR_PROFILE, typed_signature)
                .map_err(|error| invalid(error.to_string()))?;
            insert_row(
                package,
                "functions",
                &identity,
                json!({
                    "impl_hash": identity, "function_signature_hash": signature, "canonical_body": body,
                    "provided_contract_hash": provided
                }),
            )?;
            Ok(identity)
        }
        Operation::PutInterface {
            name,
            public_contract,
            previous,
            expected_hash,
            ..
        } => {
            check_edit(baseline, Table::Interfaces, previous, expected_hash)?;
            require_text(name, "interface name")?;
            let public = locals.resolve(public_contract, Table::Contracts)?;
            let identity = interface_identity(name, &public)?;
            insert_row(
                package,
                "interfaces",
                &identity,
                json!({
                    "interface_hash": identity, "name": name, "public_contract_hash": public
                }),
            )?;
            Ok(identity)
        }
        _ => unreachable!("only creations have local IDs"),
    }
}

fn create_objects(
    package: &mut Package,
    baseline: &Package,
    operations: &[Operation],
) -> Result<Locals> {
    // Resolve all creations before applying selection operations. A request may
    // place a binding or a function before the objects it refers to.
    let mut pending = BTreeMap::new();
    let mut locals = Locals {
        identities: BTreeMap::new(),
        kinds: BTreeMap::new(),
    };
    for operation in operations {
        if let Some((id, table)) = local_id(operation) {
            require_text(id, "local ID")?;
            if locals.kinds.insert(id.to_string(), table).is_some() {
                return Err(invalid(format!("duplicate local ID {id}")));
            }
            pending.insert(id, (operation, local_references(operation)?));
        }
    }
    let mut remaining = BTreeMap::new();
    let mut dependents = BTreeMap::<&str, Vec<&str>>::new();
    let mut ready = BTreeSet::new();
    for (&id, (_, refs)) in &pending {
        remaining.insert(id, refs.len());
        if refs.is_empty() {
            ready.insert(id);
        }
        for (dependency, table) in refs {
            if locals.kinds.get(*dependency) != Some(table) {
                return Err(missing(format!(
                    "local {dependency} does not identify a {}",
                    table.table()
                )));
            }
            dependents.entry(dependency).or_default().push(id);
        }
    }
    while let Some(id) = ready.pop_first() {
        let (operation, _) = pending.remove(id).expect("pending local ID");
        let identity = put(package, baseline, operation, &locals)?;
        locals.identities.insert(id.to_owned(), identity);
        for dependent in dependents.get(id).into_iter().flatten() {
            let count = remaining
                .get_mut(dependent)
                .expect("known local dependency");
            *count -= 1;
            if *count == 0 {
                ready.insert(dependent);
            }
        }
    }
    if !pending.is_empty() {
        return Err(conflict(format!(
            "cyclic local identities: {}",
            pending.keys().copied().collect::<Vec<_>>().join(", ")
        )));
    }
    Ok(locals)
}

fn references_to(
    package: &Package,
    exports: &Exports,
    selection: &Selection,
    table: Table,
    hash: &str,
) -> BTreeSet<String> {
    let mut references = BTreeSet::new();
    for (id, function) in &package.tables["functions"] {
        let found = match table {
            Table::Contracts => function["provided_contract_hash"].as_str() == Some(hash),
            _ => false,
        };
        let pin = match table {
            Table::Contracts => Some("required_contract_hash"),
            Table::Functions => Some("callee_impl_hash"),
            Table::Interfaces => None,
        };
        let mut found_in_ir = false;
        if let Some(pin) = pin {
            references_in_ir(&function["canonical_body"], pin, &mut |value| {
                found_in_ir |= value.as_str() == Some(hash);
            });
        }
        if found || found_in_ir {
            references.insert(format!("functions/{id}"));
        }
    }
    if table == Table::Contracts {
        for (id, interface) in &package.tables["interfaces"] {
            if interface["public_contract_hash"].as_str() == Some(hash) {
                references.insert(format!("interfaces/{id}"));
            }
        }
    }
    for ((name, arch, os), (interface, implementation)) in exports {
        if (table == Table::Interfaces && interface == hash)
            || (table == Table::Functions && implementation == hash)
        {
            references.insert(format!("exports/{name}/{arch}/{os}"));
        }
    }
    if table == Table::Functions && selection.entry_point.as_deref() == Some(hash) {
        references.insert("entry_point".into());
    }
    references
}

fn affected_functions(
    baseline: &Package,
    candidate: &Package,
    seeds: &BTreeSet<String>,
) -> Vec<String> {
    let mut dependents = BTreeMap::<String, BTreeSet<String>>::new();
    for graph in [baseline, candidate] {
        for (caller, function) in &graph.tables["functions"] {
            references_in_ir(
                &function["canonical_body"],
                "callee_impl_hash",
                &mut |pin| {
                    if let Some(callee) = pin.as_str() {
                        dependents
                            .entry(callee.to_owned())
                            .or_default()
                            .insert(caller.clone());
                    }
                },
            );
        }
    }
    let mut stack = seeds.iter().cloned().collect::<Vec<_>>();
    let mut affected = BTreeSet::new();
    while let Some(callee) = stack.pop() {
        for caller in dependents.get(&callee).into_iter().flatten() {
            if affected.insert(caller.clone()) {
                stack.push(caller.clone());
            }
        }
    }
    affected.into_iter().collect()
}

pub(crate) fn apply(
    package: &mut Package,
    selection: &mut Selection,
    operations: Value,
) -> Result<ChangeResult> {
    let operations: Vec<Operation> =
        serde_json::from_value(operations).map_err(|e| invalid(e.to_string()))?;
    if operations.is_empty() {
        return Err(invalid("a change set must contain at least one operation"));
    }
    let baseline = &*package;
    let mut candidate = baseline.clone();
    let mut selected = selection.clone();
    let locals = create_objects(&mut candidate, baseline, &operations)?;
    let mut exports = exports(baseline)?;
    let mut removed = BTreeMap::new();
    let mut seeds = BTreeSet::new();
    for operation in operations {
        match operation {
            Operation::SetVersion {
                version,
                expected_version,
            } => {
                require_text(&version, "version")?;
                check_expected(
                    selected.version.as_ref(),
                    expected_version.as_ref(),
                    "package version",
                )?;
                selected.version = Some(version);
            }
            Operation::PinDependency {
                name,
                snapshot_id,
                expected_snapshot_id,
            } => {
                require_text(&name, "dependency name")?;
                require_hash(&snapshot_id, "dependency snapshot ID")?;
                let deps = &mut candidate.manifest.dependencies;
                check_expected(
                    deps.get(&name),
                    expected_snapshot_id.as_ref(),
                    "dependency pin",
                )?;
                deps.insert(name, snapshot_id);
            }
            Operation::UnpinDependency {
                name,
                expected_snapshot_id,
            } => {
                let deps = &mut candidate.manifest.dependencies;
                check_expected(
                    deps.get(&name),
                    Some(&expected_snapshot_id),
                    "dependency pin",
                )?;
                deps.remove(&name);
            }
            Operation::Bind {
                interface,
                implementation,
                arch,
                os,
                expected_implementation,
            } => {
                if !llmlang_spg::valid_binding_target(&arch, &os) {
                    return Err(invalid("unregistered binding architecture or OS target"));
                }
                let interface = locals.resolve(&interface, Table::Interfaces)?;
                let implementation = locals.resolve(&implementation, Table::Functions)?;
                let name =
                    string(row(&candidate, Table::Interfaces, &interface)?, "name")?.to_owned();
                let key = (name, arch, os);
                let prior = exports.get(&key);
                check_expected(
                    prior.map(|pair| &pair.1),
                    expected_implementation.as_ref(),
                    "export binding",
                )?;
                if let Some((_, old)) = prior {
                    if old != &implementation {
                        seeds.insert(old.clone());
                    }
                }
                exports.insert(key, (interface, implementation));
            }
            Operation::Unbind {
                name,
                arch,
                os,
                expected_implementation,
            } => {
                if !llmlang_spg::valid_binding_target(&arch, &os) {
                    return Err(invalid("unregistered binding architecture or OS target"));
                }
                let key = (name, arch, os);
                check_expected(
                    exports.get(&key).map(|pair| &pair.1),
                    Some(&expected_implementation),
                    "export binding",
                )?;
                exports.remove(&key);
                seeds.insert(expected_implementation);
            }
            Operation::SetEntryPoint {
                implementation,
                expected_implementation,
            } => {
                check_expected(
                    selected.entry_point.as_ref(),
                    expected_implementation.as_ref(),
                    "entry point",
                )?;
                selected.entry_point = implementation
                    .as_ref()
                    .map(|reference| locals.resolve(reference, Table::Functions))
                    .transpose()?;
            }
            Operation::RemoveObject {
                table,
                identity,
                expected_hash,
            } => {
                let current = row(&candidate, table, &identity)?;
                check_expected(
                    Some(&hash(&identity, current)?),
                    Some(&expected_hash),
                    "removed object hash",
                )?;
                candidate
                    .tables
                    .get_mut(table.table())
                    .expect("known table")
                    .remove(&identity);
                if table == Table::Contracts {
                    candidate
                        .tables
                        .get_mut("contract_rules")
                        .expect("rules table")
                        .retain(|_, rule| rule["contract_hash"].as_str() != Some(&identity));
                }
                if table == Table::Functions {
                    seeds.insert(identity.clone());
                }
                removed.insert((table.table(), identity), table);
            }
            Operation::PutFunction {
                previous: Some(previous),
                ..
            } => {
                seeds.insert(previous);
            }
            Operation::PutContract {
                previous: Some(previous),
                ..
            } => {
                // Both provided and required contract pins affect existing paths.
                for graph in [baseline, &candidate] {
                    seeds.extend(
                        references_to(graph, &exports, &selected, Table::Contracts, &previous)
                            .into_iter()
                            .filter_map(|reference| {
                                reference.strip_prefix("functions/").map(str::to_owned)
                            }),
                    );
                }
            }
            Operation::PutInterface {
                previous: Some(previous),
                ..
            } => {
                seeds.extend(
                    exports
                        .values()
                        .filter(|(interface, _)| interface == &previous)
                        .map(|(_, implementation)| implementation.clone()),
                );
            }
            Operation::PutFunction { .. }
            | Operation::PutContract { .. }
            | Operation::PutInterface { .. } => {}
        }
    }
    for ((_, identity), table) in removed {
        let references = references_to(&candidate, &exports, &selected, table, &identity);
        if !references.is_empty() {
            return Err(conflict(format!(
                "cannot remove {identity}; retained references: {}",
                references.into_iter().collect::<Vec<_>>().join(", ")
            )));
        }
    }
    // Verification reports apply to an accepted revision and must be regenerated.
    for table in ["verification_obligations", "verification_runs"] {
        candidate
            .tables
            .get_mut(table)
            .expect("verification table")
            .clear();
    }
    write_selection(&mut candidate, &selected, &exports)?;
    let affected_functions = affected_functions(baseline, &candidate, &seeds);
    *package = candidate;
    *selection = selected;
    Ok(ChangeResult {
        identities: locals.identities,
        affected_functions,
    })
}

pub(crate) fn check_identities(
    package: &Package,
    selection: &Selection,
    resolved: &Package,
) -> Result<()> {
    let mut rules = BTreeMap::<String, BTreeSet<String>>::new();
    for (key, row) in &package.tables["contract_rules"] {
        let contract = string(row, "contract_hash")?;
        let identity = string(row, "rule_hash")?;
        let mut body = row.clone();
        let fields = body.as_object_mut().expect("rule row");
        fields.remove("contract_hash");
        fields.remove("rule_hash");
        let rule = serde_json::from_value(body)
            .map_err(|error| invalid(format!("invalid contract rule: {error}")))?;
        if rule_identity(&canonical_rule(&rule)?)? != identity
            || key != &format!("{contract}:{identity}")
        {
            return Err(invalid(format!("invalid rule identity {key}")));
        }
        rules
            .entry(contract.into())
            .or_default()
            .insert(identity.into());
    }
    for (key, row) in &package.tables["contracts"] {
        if string(row, "profile")? != SCALAR_PROFILE
            || string(row, "contract_kind")? != "function"
            || string(row, "contract_hash")? != key
            || contract_identity(
                &row["typed_signature"],
                rules.get(key).into_iter().flatten(),
            )? != *key
        {
            return Err(invalid(format!("invalid contract identity {key}")));
        }
    }
    for (key, row) in &package.tables["functions"] {
        let signature = resolved
            .function_signature(row)
            .map_err(|error| invalid(error.to_string()))?;
        if string(row, "impl_hash")? != key
            || function_identity(
                &signature.typed,
                &row["canonical_body"],
                string(row, "provided_contract_hash")?,
            )? != *key
        {
            return Err(invalid(format!("invalid function identity {key}")));
        }
    }
    for (key, row) in &package.tables["interfaces"] {
        if string(row, "interface_hash")? != key
            || interface_identity(string(row, "name")?, string(row, "public_contract_hash")?)?
                != *key
        {
            return Err(invalid(format!("invalid interface identity {key}")));
        }
    }
    let exports = exports(package)?;
    let mut candidate = package.clone();
    write_selection(&mut candidate, selection, &exports)?;
    for table in ["versions", "bindings"] {
        if candidate.tables[table] != package.tables[table] {
            return Err(invalid(format!("invalid identities in {table}")));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use llmlang_spg::Manifest;

    #[test]
    fn resolve_forward_local_references_and_reject_cycles_atomically() {
        let mut package = Package::empty(Manifest {
            language_version: "0.1.0".into(),
            dependencies: BTreeMap::new(),
        });
        let mut selection = Selection::default();
        let signature = json!({"params": [], "result": "i64"});
        let contract = json!({
            "op": "put_contract", "id": "contract", "typed_signature": signature,
            "rules": [{"kind": "ensures", "predicate": "result == 42"}]
        });
        let function = |id, body: Value| {
            json!({
                "op": "put_function", "id": id, "typed_signature": signature,
                "canonical_body": [["return", body]],
                "provided_contract": {"local": "contract"}
            })
        };
        let call = |callee| {
            json!({
                "callee_impl_hash": {"local": callee},
                "required_contract_hash": {"local": "contract"},
                "arguments": []
            })
        };
        let previous = package.clone();
        let error = apply(
            &mut package,
            &mut selection,
            json!([
                function("caller", call("callee")),
                function("callee", call("caller")),
                contract
            ]),
        )
        .unwrap_err();
        assert_eq!(error.code, "Conflict");
        assert_eq!(package, previous);

        let result = apply(
            &mut package,
            &mut selection,
            json!([
                function("caller", call("callee")),
                function("callee", json!(["i64", 42])),
                contract
            ]),
        )
        .unwrap();
        let caller = &package.tables["functions"][&result.identities["caller"]];
        assert_eq!(
            caller["canonical_body"][0][1]["callee_impl_hash"],
            result.identities["callee"],
        );
        check_identities(&package, &selection, &package).unwrap();
    }
}
