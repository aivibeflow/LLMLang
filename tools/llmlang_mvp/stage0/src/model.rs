use std::{collections::BTreeMap, fmt, marker::PhantomData};

use serde::{
    de::{self, MapAccess, Visitor},
    Deserialize, Deserializer, Serialize,
};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};

pub const SCHEMA: &str = "llmlang-spg/v1";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum Type {
    I64,
    Bool,
}

impl fmt::Display for Type {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::I64 => formatter.write_str("i64"),
            Self::Bool => formatter.write_str("bool"),
        }
    }
}

#[derive(Debug, Clone)]
pub struct Signature {
    pub params: Vec<(String, Type)>,
    pub result: Type,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Graph {
    pub schema: String,
    #[serde(deserialize_with = "unique_names")]
    pub functions: BTreeMap<String, Function>,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Function {
    pub params: Vec<(String, Type)>,
    pub result: Type,
    pub body: Vec<Value>,
    #[serde(deserialize_with = "Deserialize::deserialize")]
    pub provided_contract_hash: Option<String>,
    pub impl_hash: String,
}

#[derive(Deserialize)]
pub struct ProvidedHashes(#[serde(deserialize_with = "unique_names")] pub BTreeMap<String, String>);

fn unique_names<'de, D, T>(deserializer: D) -> Result<BTreeMap<String, T>, D::Error>
where
    D: Deserializer<'de>,
    T: Deserialize<'de>,
{
    struct UniqueNames<T>(PhantomData<T>);

    impl<'de, T: Deserialize<'de>> Visitor<'de> for UniqueNames<T> {
        type Value = BTreeMap<String, T>;

        fn expecting(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
            formatter.write_str("an object with unique function names")
        }

        fn visit_map<A: MapAccess<'de>>(self, mut map: A) -> Result<Self::Value, A::Error> {
            let mut names = BTreeMap::new();
            while let Some((name, value)) = map.next_entry::<String, T>()? {
                match names.entry(name) {
                    std::collections::btree_map::Entry::Vacant(entry) => {
                        entry.insert(value);
                    }
                    std::collections::btree_map::Entry::Occupied(entry) => {
                        return Err(de::Error::custom(format!(
                            "duplicate function name {:?}",
                            entry.key()
                        )));
                    }
                }
            }
            Ok(names)
        }
    }

    deserializer.deserialize_map(UniqueNames(PhantomData))
}

impl Function {
    pub fn identity(&self) -> String {
        // All admitted names and tags are ASCII. The value map orders object keys
        // lexicographically, including the keys of this domain-separated payload.
        let payload = json!({
            "params": self.params,
            "result": self.result,
            "body": self.body,
            "provided_contract_hash": self.provided_contract_hash,
        });
        let mut digest = Sha256::new();
        digest.update(b"llmlang-mvp/implementation/v1\0");
        digest.update(payload.to_string().as_bytes());
        format!("sha256:{:x}", digest.finalize())
    }
}

pub fn valid_hash(value: &str) -> bool {
    value.strip_prefix("sha256:").is_some_and(|digest| {
        digest.len() == 64
            && digest
                .bytes()
                .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    })
}

pub fn valid_identifier(name: &str) -> bool {
    let mut bytes = name.bytes();
    !name.starts_with("builtin__")
        && bytes
            .next()
            .is_some_and(|byte| byte == b'_' || byte.is_ascii_alphabetic())
        && bytes.all(|byte| byte == b'_' || byte.is_ascii_alphanumeric())
}

pub const ERRORS: [(&str, &str); 3] = [
    ("InvalidInput", "invalid input"),
    ("DivisionByZero", "division by zero"),
    ("ArithmeticOverflow", "arithmetic overflow"),
];

pub fn error_message(name: &str) -> Option<&'static str> {
    ERRORS
        .iter()
        .find_map(|(error, message)| (*error == name).then_some(*message))
}
