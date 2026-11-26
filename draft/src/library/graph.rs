use super::{
    invalid, open_dump, read_frame, read_index, read_manifest, Manifest, Result, HEADER, MAGIC,
    TABLES,
};
use serde::Deserialize;
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};
use std::io::{Seek, SeekFrom};
use std::path::Path;
use std::sync::Arc;

macro_rules! rows {
    ($($table:literal => $name:ident { $($field:ident: $type:ty),* $(,)? }),* $(,)?) => {
        $(#[derive(Debug, Deserialize)]
        pub struct $name { $(pub $field: $type),* })*

        #[derive(Debug)]
        pub enum Row { $($name($name)),* }

        impl Row {
            fn parse(table: &str, value: Value) -> Result<Self> {
                Ok(match table {
                    $($table => Self::$name(serde_json::from_value(value)
                        .map_err(|error| invalid(format!("{table}: {error}")))?),)*
                    _ => return Err(invalid(format!("unknown SPG table {table}"))),
                })
            }
        }
    };
}

rows! {
    "versions" => Version { version_hash: String, version: String, binding_hash: String },
    "interfaces" => Interface { interface_hash: String, name: String, public_contract_hash: String },
    "functions" => Function {
        impl_hash: String, typed_signature: Value, canonical_body: Value, provided_contract_hash: String,
    },
    "contracts" => Contract {
        contract_hash: String, contract_kind: String, profile: String,
        typed_signature: Option<Value>, state_signature: Option<Value>,
        user_request_texts: Vec<String>, review_records: Vec<Value>,
    },
    "contract_rules" => ContractRule {
        contract_hash: String, rule_hash: String, kind: String,
        error_label: Option<String>, predicate: Option<Value>, check_boundary: Option<Value>,
    },
    "bindings" => Binding { version_hash: String, interface_hash: String, impl_hash: String },
    "structures" => Structure {
        struct_impl_hash: String, type_hash: String, contract_hash: Option<String>, canonical_declaration: Value,
    },
    "structure_types" => StructureType {
        type_hash: String, identity_hash: String, aggregate_kind: String,
        ordered_member_types: Vec<Value>, representation_requirements: Value,
    },
    "structure_layouts" => StructureLayout {
        layout_hash: String, type_hash: String, target_abi_profile: Value, layout_descriptor: Value,
    },
    "structure_bindings" => StructureBinding { version_hash: String, name: String, struct_impl_hash: String },
    "verification_obligations" => VerificationObligation {
        obligation_hash: String, kind: String, caller_impl_hash: String,
        callee_impl_hash: Option<String>, struct_impl_hash: Option<String>,
        public_contract_hash: Option<String>, caller_required_contract_hash: Option<String>,
        verification_context_hash: String,
    },
    "verification_runs" => VerificationRun {
        run_id: String, obligation_hash: String, status: String, toolchain_digest: String,
        evidence_ref: String, checked_at: String,
    },
}

/// An immutable decoded row, shared by graphs that contain the same table and Content Hash.
#[derive(Debug)]
pub struct Object {
    pub table: &'static str,
    pub content_hash: String,
    pub storage_key: String,
    pub row: Row,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Relation {
    Version,
    Interface,
    Implementation,
    PublicContract,
    ProvidedContract,
    RequiredContract,
    OwningContract,
    Structure,
    StructureType,
    Caller,
    Callee,
    Obligation,
}

#[derive(Debug, Clone, Copy)]
struct Edge {
    relation: Relation,
    target: usize,
}

/// A package and the graphs supplied for its declared dependency pins.
#[derive(Debug)]
pub struct Graph {
    pub manifest: Manifest,
    objects: Vec<Arc<Object>>,
    by_table: BTreeMap<&'static str, BTreeMap<String, usize>>,
    primary: BTreeMap<(&'static str, Vec<String>), usize>,
    outgoing: Vec<Vec<Edge>>,
    incoming: Vec<Vec<Edge>>,
    calls: Vec<Vec<(usize, usize)>>,
}

impl Graph {
    /// Traverse all objects, including the selected dependencies.
    pub fn objects(&self) -> impl Iterator<Item = Node<'_>> {
        (0..self.objects.len()).map(|index| Node { graph: self, index })
    }

    /// Look up an object by its schema primary key, in declared column order.
    pub fn get(&self, table: &str, key: &[&str]) -> Option<Node<'_>> {
        let index = *self
            .primary
            .get(&(table, key.iter().map(|part| (*part).into()).collect()))?;
        Some(Node { graph: self, index })
    }

    /// Look up an object by the Content Hash recorded in its table index.
    pub fn by_content_hash(&self, table: &str, hash: &str) -> Option<Node<'_>> {
        let index = *self.by_table.get(table)?.get(hash)?;
        Some(Node { graph: self, index })
    }
}

#[derive(Clone, Copy)]
pub struct Node<'a> {
    graph: &'a Graph,
    index: usize,
}

impl<'a> Node<'a> {
    pub fn object(self) -> &'a Arc<Object> {
        &self.graph.objects[self.index]
    }

    pub fn outgoing(self) -> impl Iterator<Item = (Relation, Self)> + 'a {
        self.links(&self.graph.outgoing[self.index])
    }

    /// Exact callee and required-contract pairs derived from canonical IR.
    pub fn calls(self) -> impl Iterator<Item = (Self, Self)> + 'a {
        self.graph.calls[self.index]
            .iter()
            .map(move |&(callee, contract)| {
                (
                    Self {
                        graph: self.graph,
                        index: callee,
                    },
                    Self {
                        graph: self.graph,
                        index: contract,
                    },
                )
            })
    }

    pub fn incoming(self) -> impl Iterator<Item = (Relation, Self)> + 'a {
        self.links(&self.graph.incoming[self.index])
    }

    fn links(self, edges: &'a [Edge]) -> impl Iterator<Item = (Relation, Self)> + 'a {
        edges.iter().map(move |edge| {
            (
                edge.relation,
                Self {
                    graph: self.graph,
                    index: edge.target,
                },
            )
        })
    }
}

/// Previously loaded objects are only a cache. Declared dependencies participate in resolution.
#[derive(Default)]
pub struct GraphLoadOptions<'a> {
    pub previous: Option<&'a Graph>,
    /// Verified package graphs keyed by the exact manifest dependency identity.
    pub dependencies: BTreeMap<&'a str, &'a Graph>,
}

pub fn load_graph(
    path: &Path,
    supported_versions: &[&str],
    options: GraphLoadOptions<'_>,
) -> Result<Graph> {
    let (manifest, profile) = read_manifest(path, supported_versions)?;
    let mut graph = Graph {
        manifest,
        objects: Vec::new(),
        by_table: BTreeMap::new(),
        primary: BTreeMap::new(),
        outgoing: Vec::new(),
        incoming: Vec::new(),
        calls: Vec::new(),
    };

    let dependencies = graph
        .manifest
        .dependencies
        .iter()
        .map(|(name, pin)| {
            options
                .dependencies
                .get(pin.as_str())
                .copied()
                .ok_or_else(|| invalid(format!("missing loaded dependency {name} ({pin})")))
        })
        .collect::<Result<Vec<_>>>()?;
    for table in TABLES {
        let mut entries: Vec<_> = read_index(path, table)?.into_iter().collect();
        entries.sort_unstable_by_key(|(_, offset)| *offset);
        if entries
            .first()
            .is_some_and(|(_, offset)| *offset != MAGIC.len() as u64)
            || entries
                .windows(2)
                .any(|pair| pair[1].1 - pair[0].1 <= HEADER)
        {
            return Err(invalid(format!("{table}: invalid indexed frame offsets")));
        }
        let mut dump = if entries.is_empty() {
            let (_, size) = open_dump(path, table, profile)?;
            if size != MAGIC.len() as u64 {
                return Err(invalid(format!("{table}: empty index for nonempty dump")));
            }
            None
        } else {
            None
        };
        let mut previous_key = None::<Arc<Object>>;
        for (position, (hash, offset)) in entries.iter().enumerate() {
            let cached = options
                .previous
                .and_then(|graph| graph.by_content_hash(table, hash))
                .or_else(|| {
                    dependencies
                        .iter()
                        .find_map(|graph| graph.by_content_hash(table, hash))
                });
            let object = if let Some(node) = cached {
                Arc::clone(node.object())
            } else {
                if dump.is_none() {
                    dump = Some(open_dump(path, table, profile)?);
                }
                let (reader, size) = dump.as_mut().unwrap();
                reader.seek(SeekFrom::Start(*offset))?;
                let frame = read_frame(reader, *offset, *size, table, profile)?;
                let next = entries.get(position + 1).map_or(*size, |entry| entry.1);
                if hex::encode(frame.hash) != *hash || frame.next != next {
                    return Err(invalid(format!(
                        "{table}: index does not match frame at {offset}"
                    )));
                }
                Arc::new(Object {
                    table,
                    content_hash: hash.clone(),
                    storage_key: frame.key,
                    row: Row::parse(table, frame.row)?,
                })
            };
            if previous_key
                .as_ref()
                .is_some_and(|previous| previous.storage_key >= object.storage_key)
            {
                return Err(invalid(format!(
                    "{table}: duplicate or unordered storage key"
                )));
            }
            previous_key = Some(Arc::clone(&object));
            graph.insert(object)?;
        }
    }

    for dependency in dependencies {
        for node in dependency.objects() {
            graph.insert(Arc::clone(node.object()))?;
        }
    }
    graph.resolve()?;
    Ok(graph)
}

impl Graph {
    fn insert(&mut self, object: Arc<Object>) -> Result<()> {
        let table = self.by_table.entry(object.table).or_default();
        if table.contains_key(&object.content_hash) {
            return Ok(());
        }
        let key = object.row.primary_key();
        if key.iter().any(|part| part.is_empty()) {
            return Err(invalid(format!("{}: empty primary key", object.table)));
        }
        let index = self.objects.len();
        let key: Vec<_> = key.into_iter().map(str::to_owned).collect();
        if self
            .primary
            .insert((object.table, key.clone()), index)
            .is_some()
        {
            return Err(invalid(format!(
                "{}: conflicting primary key {key:?}",
                object.table
            )));
        }
        table.insert(object.content_hash.clone(), index);
        self.objects.push(object);
        Ok(())
    }

    fn resolve(&mut self) -> Result<()> {
        self.incoming.resize_with(self.objects.len(), Vec::new);
        for (source, object) in self.objects.iter().enumerate() {
            let mut outgoing = Vec::new();
            let references = object.row.references()?;
            for (relation, table, key) in references.pins {
                let target = self
                    .get(table, &[key])
                    .ok_or_else(|| {
                        invalid(format!(
                            "{}[{}]: missing {relation:?} target {table}[{key}]",
                            object.table, object.storage_key,
                        ))
                    })?
                    .index;
                outgoing.push(Edge { relation, target });
                self.incoming[target].push(Edge {
                    relation,
                    target: source,
                });
            }
            let calls = references
                .calls
                .into_iter()
                .map(|(callee, contract)| {
                    (
                        self.get("functions", &[callee])
                            .expect("resolved call target")
                            .index,
                        self.get("contracts", &[contract])
                            .expect("resolved call contract")
                            .index,
                    )
                })
                .collect();
            self.calls.push(calls);
            self.outgoing.push(outgoing);
        }
        Ok(())
    }
}

type Pin<'a> = (Relation, &'static str, &'a str);
type CallPins<'a> = BTreeSet<(&'a str, &'a str)>;

struct References<'a> {
    pins: BTreeSet<Pin<'a>>,
    calls: CallPins<'a>,
}

impl Row {
    fn primary_key(&self) -> Vec<&str> {
        match self {
            Self::Version(r) => vec![&r.version_hash],
            Self::Interface(r) => vec![&r.interface_hash],
            Self::Function(r) => vec![&r.impl_hash],
            Self::Contract(r) => vec![&r.contract_hash],
            Self::ContractRule(r) => vec![&r.contract_hash, &r.rule_hash],
            Self::Binding(r) => vec![&r.version_hash, &r.interface_hash],
            Self::Structure(r) => vec![&r.struct_impl_hash],
            Self::StructureType(r) => vec![&r.type_hash],
            Self::StructureLayout(r) => vec![&r.layout_hash],
            Self::StructureBinding(r) => vec![&r.version_hash, &r.name],
            Self::VerificationObligation(r) => vec![&r.obligation_hash],
            Self::VerificationRun(r) => vec![&r.run_id],
        }
    }

    fn references(&self) -> Result<References<'_>> {
        use Relation::*;
        let mut pins: BTreeSet<Pin<'_>> = BTreeSet::new();
        let mut calls = CallPins::new();
        let mut add = |relation, table, key| {
            pins.insert((relation, table, key));
        };
        match self {
            Self::Version(_) => {}
            Self::Interface(r) => add(PublicContract, "contracts", &r.public_contract_hash),
            Self::Function(r) => {
                add(ProvidedContract, "contracts", &r.provided_contract_hash);
                ir_pins(&r.typed_signature, &mut pins, &mut calls)?;
                ir_pins(&r.canonical_body, &mut pins, &mut calls)?;
            }
            Self::Contract(r) => {
                let signature = match (&*r.contract_kind, &r.typed_signature, &r.state_signature) {
                    ("function", Some(signature), None)
                    | ("structure" | "domain", None, Some(signature)) => signature,
                    _ => return Err(invalid("contract kind and signature do not agree")),
                };
                ir_pins(signature, &mut pins, &mut calls)?;
            }
            Self::ContractRule(r) => {
                add(OwningContract, "contracts", &r.contract_hash);
                for ir in [&r.predicate, &r.check_boundary].into_iter().flatten() {
                    ir_pins(ir, &mut pins, &mut calls)?;
                }
            }
            Self::Binding(r) => {
                add(Version, "versions", &r.version_hash);
                add(Interface, "interfaces", &r.interface_hash);
                add(Implementation, "functions", &r.impl_hash);
            }
            Self::Structure(r) => {
                add(StructureType, "structure_types", &r.type_hash);
                if let Some(hash) = &r.contract_hash {
                    add(OwningContract, "contracts", hash);
                }
                ir_pins(&r.canonical_declaration, &mut pins, &mut calls)?;
            }
            Self::StructureType(r) => {
                for ir in &r.ordered_member_types {
                    ir_pins(ir, &mut pins, &mut calls)?;
                }
            }
            Self::StructureLayout(r) => add(StructureType, "structure_types", &r.type_hash),
            Self::StructureBinding(r) => {
                add(Version, "versions", &r.version_hash);
                add(Structure, "structures", &r.struct_impl_hash);
            }
            Self::VerificationObligation(r) => {
                add(Caller, "functions", &r.caller_impl_hash);
                match (
                    &*r.kind,
                    &r.callee_impl_hash,
                    &r.struct_impl_hash,
                    &r.public_contract_hash,
                    &r.caller_required_contract_hash,
                ) {
                    ("body_conformance", None, None, None, None) => {}
                    ("call_compatibility", Some(callee), None, None, Some(required)) => {
                        add(Callee, "functions", callee);
                        add(RequiredContract, "contracts", required);
                    }
                    ("public_refinement", None, None, Some(public), None) => {
                        add(PublicContract, "contracts", public)
                    }
                    ("structure_contract_check", None, Some(structure), None, None) => {
                        add(Structure, "structures", structure)
                    }
                    _ => {
                        return Err(invalid(
                            "verification obligation kind and references do not agree",
                        ))
                    }
                }
            }
            Self::VerificationRun(r) => {
                add(Obligation, "verification_obligations", &r.obligation_hash)
            }
        }
        Ok(References { pins, calls })
    }
}

fn ir_pins<'a>(
    ir: &'a Value,
    pins: &mut BTreeSet<Pin<'a>>,
    calls: &mut CallPins<'a>,
) -> Result<()> {
    match ir {
        Value::Object(object) => {
            if let Some(hash) = object.get("struct_impl_hash") {
                pins.insert((Relation::Structure, "structures", pin_str(hash)?));
            }
            match (
                object.get("callee_impl_hash"),
                object.get("required_contract_hash"),
            ) {
                (Some(callee), Some(required)) => {
                    let callee = pin_str(callee)?;
                    let required = pin_str(required)?;
                    calls.insert((callee, required));
                    pins.insert((Relation::Callee, "functions", callee));
                    pins.insert((Relation::RequiredContract, "contracts", required));
                }
                (None, None) => {}
                _ => {
                    return Err(invalid(
                        "canonical call requires both callee and required contract pins",
                    ))
                }
            }
            for child in object.values() {
                ir_pins(child, pins, calls)?;
            }
        }
        Value::Array(items) => {
            for child in items {
                ir_pins(child, pins, calls)?;
            }
        }
        _ => {}
    }
    Ok(())
}

fn pin_str(value: &Value) -> Result<&str> {
    value
        .as_str()
        .ok_or_else(|| invalid("canonical IR pin must be a string"))
}
