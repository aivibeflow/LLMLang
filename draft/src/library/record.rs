use crate::{invalid, Error, Result};
use prost::Message;
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};

#[allow(clippy::enum_variant_names)]
mod wire {
    include!(concat!(env!("OUT_DIR"), "/llmlang.spg.storage.v6.rs"));
}

use wire::{value::Kind, Field, List, Object, Value as WireValue};

impl Object {
    fn encode_fields(fields: &Map<String, Value>, depth: usize) -> Result<Self> {
        let mut sorted: Vec<_> = fields.iter().collect();
        sorted.sort_unstable_by(|(left, _), (right, _)| left.cmp(right));
        let fields = sorted
            .into_iter()
            .map(|(key, value)| {
                Ok(Field {
                    key: key.clone(),
                    value: Some(WireValue::from_value(value, depth)?),
                })
            })
            .collect::<Result<_>>()?;
        Ok(Self { fields })
    }

    fn logical(&self) -> Result<Map<String, Value>> {
        let mut values = Map::new();
        let mut previous = None;
        for field in &self.fields {
            if previous.is_some_and(|key: &str| key >= field.key.as_str()) {
                return Err(invalid("duplicate or unordered Protobuf object fields"));
            }
            previous = Some(field.key.as_str());
            values.insert(
                field.key.clone(),
                field
                    .value
                    .as_ref()
                    .ok_or_else(|| invalid("missing Protobuf field value"))?
                    .logical()?,
            );
        }
        Ok(values)
    }

    fn proto_json(&self) -> Value {
        if self.fields.is_empty() {
            return json!({});
        }
        let fields: Vec<_> = self
            .fields
            .iter()
            .map(|field| {
                let mut result = Map::new();
                if !field.key.is_empty() {
                    result.insert("key".into(), json!(field.key));
                }
                result.insert("value".into(), field.value.as_ref().unwrap().proto_json());
                result
            })
            .collect();
        json!({"fields": fields})
    }
}

impl WireValue {
    fn from_value(value: &Value, depth: usize) -> Result<Self> {
        if depth > 24 {
            return Err(invalid("record exceeds nesting limit"));
        }
        let kind = match value {
            Value::Null => Kind::NullValue(true),
            Value::Bool(value) => Kind::BoolValue(*value),
            Value::Number(value) => Kind::IntValue(
                value
                    .as_i64()
                    .ok_or_else(|| invalid("record number must be a signed 64-bit integer"))?,
            ),
            Value::String(value) => Kind::StringValue(value.clone()),
            Value::Array(values) => Kind::ListValue(List {
                values: values
                    .iter()
                    .map(|value| Self::from_value(value, depth + 1))
                    .collect::<Result<_>>()?,
            }),
            Value::Object(fields) => Kind::ObjectValue(Object::encode_fields(fields, depth + 1)?),
        };
        Ok(Self { kind: Some(kind) })
    }

    fn logical(&self) -> Result<Value> {
        Ok(match &self.kind {
            Some(Kind::NullValue(true)) => Value::Null,
            Some(Kind::BoolValue(value)) => json!(value),
            Some(Kind::IntValue(value)) => json!(value),
            Some(Kind::StringValue(value)) => json!(value),
            Some(Kind::ListValue(list)) => Value::Array(
                list.values
                    .iter()
                    .map(Self::logical)
                    .collect::<Result<_>>()?,
            ),
            Some(Kind::ObjectValue(object)) => Value::Object(object.logical()?),
            _ => return Err(invalid("invalid or missing Protobuf value kind")),
        })
    }

    fn proto_json(&self) -> Value {
        match self.kind.as_ref().unwrap() {
            Kind::NullValue(value) => json!({"nullValue": value}),
            Kind::BoolValue(value) => json!({"boolValue": value}),
            Kind::IntValue(value) => json!({"intValue": value.to_string()}),
            Kind::StringValue(value) => json!({"stringValue": value}),
            Kind::ListValue(list) if list.values.is_empty() => json!({"listValue": {}}),
            Kind::ListValue(list) => json!({"listValue": {"values": list.values.iter()
                .map(Self::proto_json).collect::<Vec<_>>()}}),
            Kind::ObjectValue(object) => json!({"objectValue": object.proto_json()}),
        }
    }
}

/// Compute the logical Content Hash independently of the table encoding.
pub fn content_hash(key: &str, row: &Value) -> Result<String> {
    if key.is_empty() {
        return Err(invalid("record key is empty"));
    }
    let fields = row
        .as_object()
        .ok_or_else(|| invalid("record content must be an object"))?;
    Object::encode_fields(fields, 0)?;
    Ok(hex::encode(digest(key, row)?))
}

pub(crate) fn canonical_json(value: &Value, output: &mut Vec<u8>) -> Result<()> {
    match value {
        Value::Object(fields) => {
            output.push(b'{');
            let fields: std::collections::BTreeMap<_, _> = fields.iter().collect();
            for (index, (key, value)) in fields.into_iter().enumerate() {
                if index > 0 {
                    output.push(b',');
                }
                serde_json::to_writer(&mut *output, key)?;
                output.push(b':');
                canonical_json(value, output)?;
            }
            output.push(b'}');
        }
        Value::Array(values) => {
            output.push(b'[');
            for (index, value) in values.iter().enumerate() {
                if index > 0 {
                    output.push(b',');
                }
                canonical_json(value, output)?;
            }
            output.push(b']');
        }
        _ => serde_json::to_writer(output, value)?,
    }
    Ok(())
}

pub(crate) fn digest(key: &str, row: &Value) -> Result<[u8; 32]> {
    let mut material = b"llmlang-spg-content/v1\0".to_vec();
    canonical_json(&json!({"key": key, "content": row}), &mut material)?;
    Ok(Sha256::digest(material).into())
}

trait Column: Sized {
    fn read(value: Option<&Value>) -> Result<Self>;
    fn logical(&self) -> Result<Option<Value>>;
    fn proto_json(&self) -> Option<Value>;
}

impl<T: Column> Column for Option<T> {
    fn read(value: Option<&Value>) -> Result<Self> {
        value.map(|value| T::read(Some(value))).transpose()
    }

    fn logical(&self) -> Result<Option<Value>> {
        match self {
            Some(value) => value.logical(),
            None => Ok(None),
        }
    }

    fn proto_json(&self) -> Option<Value> {
        self.as_ref().and_then(T::proto_json)
    }
}

impl<T: Column> Column for Vec<T> {
    fn read(value: Option<&Value>) -> Result<Self> {
        value
            .and_then(Value::as_array)
            .ok_or_else(|| invalid("expected array column"))?
            .iter()
            .map(|element| T::read(Some(element)))
            .collect()
    }

    fn logical(&self) -> Result<Option<Value>> {
        let values = self
            .iter()
            .map(|element| {
                element
                    .logical()?
                    .ok_or_else(|| invalid("missing repeated column element"))
            })
            .collect::<Result<Vec<_>>>()?;
        Ok(Some(Value::Array(values)))
    }

    fn proto_json(&self) -> Option<Value> {
        (!self.is_empty()).then(|| Value::Array(self.iter().filter_map(T::proto_json).collect()))
    }
}

// The generated repeated fields contain concrete strings or messages, so their
// individual element conversions use the same rules as present singular fields.
impl Column for String {
    fn read(value: Option<&Value>) -> Result<Self> {
        value
            .and_then(Value::as_str)
            .map(str::to_owned)
            .ok_or_else(|| invalid("expected string column"))
    }
    fn logical(&self) -> Result<Option<Value>> {
        Ok(self.proto_json())
    }
    fn proto_json(&self) -> Option<Value> {
        Some(json!(self))
    }
}

impl Column for WireValue {
    fn read(value: Option<&Value>) -> Result<Self> {
        WireValue::from_value(value.ok_or_else(|| invalid("missing value"))?, 0)
    }
    fn logical(&self) -> Result<Option<Value>> {
        WireValue::logical(self).map(Some)
    }
    fn proto_json(&self) -> Option<Value> {
        Some(WireValue::proto_json(self))
    }
}

macro_rules! table_records {
    ($($table:literal => $variant:ident($name:ident) [$($primary:ident),+] {
        $($field:ident: ($required:literal, $json_name:literal)),* $(,)?
    }),* $(,)?) => {
        pub(crate) enum TableRecord {
            $($variant(wire::$name)),*
        }

        impl TableRecord {
            fn key(table: &str, row: &Value) -> Result<String> {
                match table {
                    $($table => {
                        let parts = [$(
                            row[stringify!($primary)].as_str()
                                .filter(|value| match stringify!($primary) {
                                    "platform" => super::valid_binding_platform(value),
                                    _ => !value.is_empty(),
                                })
                                .ok_or_else(|| invalid(concat!($table, ": missing or invalid primary key column ", stringify!($primary))))?
                        ),+];
                        Ok(parts.join(":"))
                    }),*
                    _ => Err(invalid(format!("unknown SPG table {table}"))),
                }
            }

            pub(crate) fn new(table: &str, key: &str, row: &Value) -> Result<Self> {
                if key.is_empty() {
                    return Err(invalid("record key is empty"));
                }
                let fields = row.as_object().ok_or_else(|| invalid("record content must be an object"))?;
                match table {
                    $($table => {
                        for field in fields.keys() {
                            if ![$(stringify!($field)),*].contains(&field.as_str()) {
                                return Err(invalid(format!("{table}: unknown column {field}")));
                            }
                        }
                        match table {
                            "function_signatures" => {
                                let text = row["function_signature_content"].as_str()
                                    .ok_or_else(|| invalid("missing function signature content"))?;
                                super::resolve_function_signature(key, text)?;
                            }
                            "functions" => {
                                let hash = row["function_signature_hash"].as_str()
                                    .ok_or_else(|| invalid("missing function signature hash"))?;
                                super::check_hash(hash.strip_prefix("sha256:")
                                    .ok_or_else(|| invalid("invalid function signature hash"))?)?;
                                super::signature::validate_block(row["canonical_body"].as_str()
                                    .ok_or_else(|| invalid("canonical body must be source text"))?)?;
                            }
                            _ => {}
                        }
                        if key != Self::key(table, row)? {
                            return Err(invalid(format!("{table}: row key does not match primary key columns")));
                        }
                        Ok(Self::$variant(wire::$name {
                            $($field: {
                                let value = fields.get(stringify!($field));
                                if $required && value.is_none() {
                                    return Err(invalid(concat!($table, ": missing column ", stringify!($field))));
                                }
                                Column::read(value)?
                            }),*
                        }))
                    }),*
                    _ => Err(invalid(format!("unknown SPG table {table}"))),
                }
            }

            pub(crate) fn parse(table: &str, raw: &[u8]) -> Result<(Self, String, Value)> {
                match table {
                    $($table => {
                        let record = wire::$name::decode(raw).map_err(Error::Protobuf)?;
                        let mut fields = Map::new();
                        $(if let Some(value) = Column::logical(&record.$field)? {
                            fields.insert(stringify!($field).into(), value);
                        })*
                        let row = Value::Object(fields);
                        let key = Self::key(table, &row)?;
                        if Self::new(table, &key, &row)?.encode_to_vec() != raw {
                            return Err(invalid(format!("{table}: noncanonical Protobuf record")));
                        }
                        Ok((Self::$variant(record), key, row))
                    }),*
                    _ => Err(invalid(format!("unknown SPG table {table}"))),
                }
            }

            pub(crate) fn encode_to_vec(&self) -> Vec<u8> {
                match self {
                    $(Self::$variant(record) => record.encode_to_vec()),*
                }
            }

            pub(crate) fn proto_json(&self) -> Value {
                match self {
                    $(Self::$variant(record) => {
                        let mut result = Map::new();
                        $(if let Some(value) = Column::proto_json(&record.$field) {
                            result.insert($json_name.into(), value);
                        })*
                        Value::Object(result)
                    }),*
                }
            }
        }
    };
}
table_records! {
    "versions" => Version(VersionRecord) [version_hash] {
        version_hash: (true, "versionHash"),
        version: (true, "version"),
        binding_hash: (true, "bindingHash"),
    },
    "interfaces" => Interface(InterfaceRecord) [interface_hash] {
        interface_hash: (true, "interfaceHash"),
        name: (true, "name"),
        public_contract_hash: (true, "publicContractHash"),
    },
    "function_signatures" => FunctionSignature(FunctionSignatureRecord) [function_signature_hash] {
        function_signature_hash: (true, "functionSignatureHash"),
        function_signature_content: (true, "functionSignatureContent"),
    },
    "functions" => Function(FunctionRecord) [impl_hash] {
        impl_hash: (true, "implHash"),
        function_signature_hash: (true, "functionSignatureHash"),
        canonical_body: (true, "canonicalBody"),
        provided_contract_hash: (true, "providedContractHash"),
    },
    "contracts" => Contract(ContractRecord) [contract_hash] {
        contract_hash: (true, "contractHash"),
        contract_kind: (true, "contractKind"),
        profile: (true, "profile"),
        typed_signature: (false, "typedSignature"),
        state_signature: (false, "stateSignature"),
        user_request_texts: (true, "userRequestTexts"),
        review_records: (true, "reviewRecords"),
    },
    "contract_rules" => ContractRule(ContractRuleRecord) [contract_hash, rule_hash] {
        contract_hash: (true, "contractHash"),
        rule_hash: (true, "ruleHash"),
        kind: (true, "kind"),
        error_label: (false, "errorLabel"),
        predicate: (false, "predicate"),
        check_boundary: (false, "checkBoundary"),
    },
    "bindings" => Binding(BindingRecord) [version_hash, interface_hash, platform] {
        version_hash: (true, "versionHash"),
        interface_hash: (true, "interfaceHash"),
        impl_hash: (true, "implHash"),
        platform: (true, "platform"),
    },
    "structures" => Structure(StructureRecord) [struct_impl_hash] {
        struct_impl_hash: (true, "structImplHash"),
        type_hash: (true, "typeHash"),
        contract_hash: (false, "contractHash"),
        canonical_declaration: (true, "canonicalDeclaration"),
    },
    "structure_types" => StructureType(StructureTypeRecord) [type_hash] {
        type_hash: (true, "typeHash"),
        identity_hash: (true, "identityHash"),
        aggregate_kind: (true, "aggregateKind"),
        ordered_member_types: (true, "orderedMemberTypes"),
        representation_requirements: (true, "representationRequirements"),
    },
    "structure_layouts" => StructureLayout(StructureLayoutRecord) [layout_hash] {
        layout_hash: (true, "layoutHash"),
        type_hash: (true, "typeHash"),
        target_abi_profile: (true, "targetAbiProfile"),
        layout_descriptor: (true, "layoutDescriptor"),
    },
    "structure_bindings" => StructureBinding(StructureBindingRecord) [version_hash, name] {
        version_hash: (true, "versionHash"),
        name: (true, "name"),
        struct_impl_hash: (true, "structImplHash"),
    },
    "verification_obligations" => VerificationObligation(VerificationObligationRecord) [obligation_hash] {
        obligation_hash: (true, "obligationHash"),
        kind: (true, "kind"),
        caller_impl_hash: (true, "callerImplHash"),
        callee_impl_hash: (false, "calleeImplHash"),
        struct_impl_hash: (false, "structImplHash"),
        public_contract_hash: (false, "publicContractHash"),
        caller_required_contract_hash: (false, "callerRequiredContractHash"),
        verification_context_hash: (true, "verificationContextHash"),
    },
    "verification_runs" => VerificationRun(VerificationRunRecord) [run_id] {
        run_id: (true, "runId"),
        obligation_hash: (true, "obligationHash"),
        status: (true, "status"),
        toolchain_digest: (true, "toolchainDigest"),
        evidence_ref: (true, "evidenceRef"),
        checked_at: (true, "checkedAt"),
    },
}
