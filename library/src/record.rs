use crate::{invalid, Error, Result};
use prost::Message;
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};

// Wire schema shared with packages/linux.syscalls/storage.proto.
#[derive(Clone, PartialEq, Message)]
pub(crate) struct Record {
    #[prost(string, tag = "1")]
    key: String,
    #[prost(message, optional, tag = "2")]
    content: Option<Object>,
}

#[derive(Clone, PartialEq, Message)]
struct Object {
    #[prost(message, repeated, tag = "1")]
    fields: Vec<Field>,
}

#[derive(Clone, PartialEq, Message)]
struct Field {
    #[prost(string, tag = "1")]
    key: String,
    #[prost(message, optional, tag = "2")]
    value: Option<WireValue>,
}

#[derive(Clone, PartialEq, Message)]
struct List {
    #[prost(message, repeated, tag = "1")]
    values: Vec<WireValue>,
}

#[derive(Clone, PartialEq, Message)]
struct WireValue {
    #[prost(oneof = "Kind", tags = "1, 2, 3, 4, 5, 6")]
    kind: Option<Kind>,
}

#[derive(Clone, PartialEq, prost::Oneof)]
enum Kind {
    #[prost(bool, tag = "1")]
    Null(bool),
    #[prost(bool, tag = "2")]
    Bool(bool),
    #[prost(sint64, tag = "3")]
    Int(i64),
    #[prost(string, tag = "4")]
    String(String),
    #[prost(message, tag = "5")]
    List(List),
    #[prost(message, tag = "6")]
    Object(Object),
}

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
            Value::Null => Kind::Null(true),
            Value::Bool(value) => Kind::Bool(*value),
            Value::Number(value) => Kind::Int(
                value
                    .as_i64()
                    .ok_or_else(|| invalid("record number must be a signed 64-bit integer"))?,
            ),
            Value::String(value) => Kind::String(value.clone()),
            Value::Array(values) => Kind::List(List {
                values: values
                    .iter()
                    .map(|value| Self::from_value(value, depth + 1))
                    .collect::<Result<_>>()?,
            }),
            Value::Object(fields) => Kind::Object(Object::encode_fields(fields, depth + 1)?),
        };
        Ok(Self { kind: Some(kind) })
    }

    fn logical(&self) -> Result<Value> {
        Ok(match &self.kind {
            Some(Kind::Null(true)) => Value::Null,
            Some(Kind::Bool(value)) => json!(value),
            Some(Kind::Int(value)) => json!(value),
            Some(Kind::String(value)) => json!(value),
            Some(Kind::List(list)) => Value::Array(
                list.values
                    .iter()
                    .map(Self::logical)
                    .collect::<Result<_>>()?,
            ),
            Some(Kind::Object(object)) => Value::Object(object.logical()?),
            _ => return Err(invalid("invalid or missing Protobuf value kind")),
        })
    }

    fn proto_json(&self) -> Value {
        match self.kind.as_ref().unwrap() {
            Kind::Null(value) => json!({"nullValue": value}),
            Kind::Bool(value) => json!({"boolValue": value}),
            Kind::Int(value) => json!({"intValue": value.to_string()}),
            Kind::String(value) => json!({"stringValue": value}),
            Kind::List(list) if list.values.is_empty() => json!({"listValue": {}}),
            Kind::List(list) => json!({"listValue": {"values": list.values.iter()
                .map(Self::proto_json).collect::<Vec<_>>()}}),
            Kind::Object(object) => json!({"objectValue": object.proto_json()}),
        }
    }
}

impl Record {
    pub(crate) fn new(key: &str, row: &Value) -> Result<Self> {
        if key.is_empty() {
            return Err(invalid("record key is empty"));
        }
        let fields = row
            .as_object()
            .ok_or_else(|| invalid("record content must be an object"))?;
        Ok(Self {
            key: key.into(),
            content: Some(Object::encode_fields(fields, 0)?),
        })
    }

    pub(crate) fn parse(raw: &[u8]) -> Result<(Self, String, Value)> {
        let record = Self::decode(raw).map_err(Error::Protobuf)?;
        let row = Value::Object(
            record
                .content
                .as_ref()
                .ok_or_else(|| invalid("missing Protobuf record content"))?
                .logical()?,
        );
        if Self::new(&record.key, &row)?.encode_to_vec() != raw {
            return Err(invalid("noncanonical Protobuf record"));
        }
        let key = record.key.clone();
        Ok((record, key, row))
    }

    pub(crate) fn proto_json(&self) -> Value {
        json!({"key": self.key, "content": self.content.as_ref().unwrap().proto_json()})
    }
}

fn canonical_json(value: &Value, output: &mut Vec<u8>) -> Result<()> {
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
